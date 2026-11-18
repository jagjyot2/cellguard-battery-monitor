"""Verification tests for CellGuard's simulator-independent HAL, Wokwi config, and preserved BenchTwin."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

from backend.analytics import PackAnalyticsEngine, PackConfiguration, ThermalDerivativeTracker
from simulation.adapters.common.battery_hal_interface import SafetyCapabilities
from simulation.adapters.wokwi.wokwi_cellguard_adapter import WokwiCellGuardAdapter

ROOT = Path(__file__).resolve().parent.parent


def _parse_config_pins(config_text: str) -> dict[str, int]:
    pins: dict[str, int] = {}
    for name, val in re.findall(r"constexpr\s+uint8_t\s+(PIN_[A-Z0-9_]+)\s*=\s*(\d+);", config_text):
        pins[name] = int(val)
    return pins


def test_wokwi_diagram_pins_match_firmware_config() -> None:
    cfg_text = (ROOT / "firmware" / "include" / "cellguard_config.h").read_text(encoding="utf-8")
    pins = _parse_config_pins(cfg_text)

    diagram = json.loads((ROOT / "wokwi" / "diagram.json").read_text(encoding="utf-8"))
    assert diagram["version"] == 1
    part_types = {p["id"]: p["type"] for p in diagram["parts"]}
    assert part_types["esp"] == "board-esp32-devkit-c-v4"
    assert part_types["ina226"] == "chip-ina226"
    assert part_types["mux"] == "chip-cd74hc4051"
    assert part_types["led_alarm"] == "wokwi-led"
    assert part_types["led_status"] == "wokwi-led"

    # Collect ESP32 pin -> target endpoint pairs
    esp_links: dict[str, set[str]] = {}
    for src, dst, *_ in diagram["connections"]:
        if src.startswith("esp:"):
            esp_links.setdefault(src.split(":", 1)[1], set()).add(dst)
        if dst.startswith("esp:"):
            esp_links.setdefault(dst.split(":", 1)[1], set()).add(src)

    # On Wokwi board-esp32-devkit-c-v4, GPIO36 is VP and GPIO39 is VN
    gpio_to_wokwi = {36: "VP", 39: "VN"}
    expected_targets = {
        "PIN_I2C_SDA": "ina226:SDA",
        "PIN_I2C_SCL": "ina226:SCL",
        "PIN_INA_ALERT": "ina226:ALERT",
        "PIN_CELL_MUX_ADC": "mux:COM_OUT",
        "PIN_MUX_S0": "mux:S0",
        "PIN_MUX_S1": "mux:S1",
        "PIN_MUX_S2": "mux:S2",
        "PIN_NTC_0": "ntc0:OUT",
        "PIN_NTC_1": "ntc1:OUT",
        "PIN_NTC_2": "ntc2:OUT",
        "PIN_NTC_3": "ntc3:OUT",
        "PIN_LED_ALARM": "led_alarm:A",
        "PIN_LED_STATUS": "led_status:A",
        "PIN_BUZZER_ALERT": "buzzer_alert:1",
        "PIN_CAL_BTN": "btn_cal:1.l",
    }
    for pin_name, target in expected_targets.items():
        gpio_num = pins[pin_name]
        wokwi_pin = gpio_to_wokwi.get(gpio_num, str(gpio_num))
        assert target in esp_links.get(wokwi_pin, set()), (
            f"{pin_name} (GPIO{gpio_num}/esp:{wokwi_pin}) missing connection to {target}"
        )


def test_wokwi_toml_and_custom_chips_valid() -> None:
    toml_data = tomllib.loads((ROOT / "wokwi" / "wokwi.toml").read_text(encoding="utf-8"))
    wokwi_cfg = toml_data["wokwi"]
    assert wokwi_cfg["version"] == 1
    assert wokwi_cfg["firmware"] == "../firmware/.pio/build/esp32dev/firmware.bin"
    assert wokwi_cfg["elf"] == "../firmware/.pio/build/esp32dev/firmware.elf"

    chips = {c["name"] for c in toml_data.get("chip", [])}
    assert {"chip-ina226", "chip-cd74hc4051"}.issubset(chips)
    for chip_name in ("chip-ina226", "chip-cd74hc4051"):
        assert (ROOT / "wokwi" / f"{chip_name}.chip.json").is_file()
        assert (ROOT / "wokwi" / f"{chip_name}.chip.c").is_file()


def test_scenarios_through_wokwi_adapter_and_analytics() -> None:
    scenarios_dir = ROOT / "simulation" / "scenarios"

    # 1. 4S Nominal Discharge
    adapter_4s = WokwiCellGuardAdapter(scenarios_dir / "4s_nominal_discharge.json")
    assert adapter_4s.backend_name == "wokwi"
    frame_4s = adapter_4s.step_and_sample(10.0)
    assert frame_4s.ina226.alert_active is False
    assert frame_4s.ina226.current_a == pytest.approx(10.0, abs=0.01)
    assert len(frame_4s.cell_taps.cell_voltages_v) == 4

    # 2. 6S Overcurrent Sag Alarm
    adapter_6s = WokwiCellGuardAdapter(scenarios_dir / "6s_overcurrent_sag_alarm.json")
    eng_6s = PackAnalyticsEngine(PackConfiguration(series_cells=6))
    frame_6s = adapter_6s.step_and_sample(12.0)
    assert frame_6s.ina226.alert_active is True
    assert frame_6s.ina226.current_a > 45.0
    snap_6s = eng_6s.step(
        timestamp_s=12.0,
        pack_voltage_v=frame_6s.ina226.bus_voltage_v,
        current_a=frame_6s.ina226.current_a,
        cell_voltages_v=frame_6s.cell_taps.cell_voltages_v,
        temps_c=frame_6s.ntc.temperatures_c,
        ina_hw_alert=frame_6s.ina226.alert_active,
    )
    codes_6s = set(snap_6s.alarm_codes)
    assert {"OC_DISCHARGE", "CELL_UV_CRIT", "CELL_DELTA_CRIT", "INA_HW_ALERT"}.issubset(codes_6s)

    # 3. NTC Thermal Runaway dT/dt
    adapter_ntc = WokwiCellGuardAdapter(scenarios_dir / "ntc_thermal_runaway_dtdt.json")
    tracker = ThermalDerivativeTracker(window_size=12, num_channels=4)
    eng_ntc = PackAnalyticsEngine(PackConfiguration(series_cells=4))
    slope = 0.0
    for t_s in range(0, 65, 5):
        frame_step = adapter_ntc.step_and_sample(float(t_s))
        slope = tracker.push(0, frame_step.ntc.temperatures_c[0], float(t_s))
        eng_ntc.step(
            timestamp_s=float(t_s),
            pack_voltage_v=frame_step.ina226.bus_voltage_v,
            current_a=frame_step.ina226.current_a,
            cell_voltages_v=frame_step.cell_taps.cell_voltages_v,
            temps_c=frame_step.ntc.temperatures_c,
            ina_hw_alert=frame_step.ina226.alert_active,
        )
    assert slope >= 5.0
    frame_hot = adapter_ntc.step_and_sample(120.0)
    snap_hot = eng_ntc.step(
        timestamp_s=120.0,
        pack_voltage_v=frame_hot.ina226.bus_voltage_v,
        current_a=frame_hot.ina226.current_a,
        cell_voltages_v=frame_hot.cell_taps.cell_voltages_v,
        temps_c=frame_hot.ntc.temperatures_c,
        ina_hw_alert=frame_hot.ina226.alert_active,
    )
    codes_hot = set(snap_hot.alarm_codes)
    assert {"THERMAL_RUNAWAY_CRIT", "TEMP_CRIT"}.issubset(codes_hot)


def test_monitor_only_safety_and_component_matrix() -> None:
    caps = SafetyCapabilities()
    caps.validate()
    assert caps.monitor_only is True
    assert caps.balancing_supported is False
    assert caps.charging_supported is False
    assert caps.fet_switching_supported is False

    hal_h = (ROOT / "simulation" / "adapters" / "common" / "battery_hal_interface.h").read_text(encoding="utf-8")
    assert "CELLGUARD_MONITOR_ONLY" in hal_h
    assert "balancing_supported     = false" in hal_h

    matrix = (ROOT / "simulation" / "documentation" / "COMPONENT-SUPPORT-MATRIX.md").read_text(encoding="utf-8")
    assert "UNSUPPORTED NATIVELY" in matrix
    assert "chip-ina226" in matrix
    assert "CD74HC4051" in matrix
    assert "wokwi-ntc-temperature-sensor" in matrix


def test_preserved_benchtwin_integrity() -> None:
    bt_dir = ROOT / "benchtwin"
    expected_files = [
        "BENCHTWIN-SIMULATION-NOTES.md",
        "BOM.csv",
        "cellguard-benchtwin.json",
        "cellguard.btw",
        "cellguard.net",
        "cellguard_enclosure.stl",
    ]
    for fname in expected_files:
        assert (bt_dir / fname).is_file(), f"Preserved BenchTwin file missing: {fname}"

    bt_manifest = json.loads((bt_dir / "cellguard-benchtwin.json").read_text(encoding="utf-8"))
    assert bt_manifest["project"]["safety_classification"] == "NON_INVASIVE_MONITOR_ONLY"
    assert bt_manifest["project"]["external_bms_and_fuse_required"] is True

    adapter_manifest = json.loads(
        (ROOT / "simulation" / "adapters" / "benchtwin" / "benchtwin_adapter_manifest.json").read_text(encoding="utf-8")
    )
    assert adapter_manifest["status"] == "preserved_inactive"
    assert adapter_manifest["active_simulator"] == "wokwi"
    assert adapter_manifest["safety_invariant"]["monitor_only"] is True
