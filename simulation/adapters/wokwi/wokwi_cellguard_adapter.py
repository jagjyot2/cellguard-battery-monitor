"""Wokwi HAL Adapter for CellGuard (Simulator-Independent Abstraction Layer).

Bridges CellGuard's canonical `BatteryHALInterface` to Wokwi simulations and
scenario-driven validation runs. Explicitly documents mocked/custom components:
- ESP32 (`board-esp32-devkit-c-v4`), NTC probes (`wokwi-ntc-temperature-sensor`),
  analog divider pots (`wokwi-potentiometer`), and alarm LEDs (`wokwi-led`)
  are natively supported in Wokwi.
- `INA226` (0x40) is unsupported natively in Wokwi -> backed by custom Wokwi
  I2C chip `chip-ina226` (`wokwi/chip-ina226.chip.json`/`.c`) and this adapter.
- `CD74HC4051` 8:1 MUX is unsupported natively in Wokwi -> backed by direct
  analog tap/potentiometer stub + documented software mock.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List

from simulation.adapters.common.battery_hal_interface import (
    AlarmOutputState,
    BatteryHALInterface,
    CellTapTelemetry,
    INA226Telemetry,
    NTCTelemetry,
)

# Steinhart-Hart defaults matching firmware/include/drivers/ntc_array.h
_SH_A = 1.129148e-3
_SH_B = 2.34125e-4
_SH_C = 8.76741e-8


def celsius_to_ntc_resistance(temp_c: float) -> float:
    """Invert Steinhart-Hart equation to compute 10k NTC resistance at temp_c."""
    t_k = max(200.0, temp_c + 273.15)
    x = (1.0 / t_k - _SH_A) / _SH_C
    y = math.sqrt((_SH_B / (3.0 * _SH_C)) ** 3 + (x / 2.0) ** 2)
    ln_r = (y - x / 2.0) ** (1.0 / 3.0) - (y + x / 2.0) ** (1.0 / 3.0)
    # Handle negative cube root cleanly
    half_x = x / 2.0
    term1 = math.copysign(abs(y - half_x) ** (1.0 / 3.0), y - half_x)
    term2 = math.copysign(abs(y + half_x) ** (1.0 / 3.0), y + half_x)
    ln_r = term1 - term2
    return math.exp(ln_r)


class WokwiCellGuardAdapter(BatteryHALInterface):
    """Wokwi simulation adapter implementing BatteryHALInterface."""

    def __init__(self, scenario_path: str | Path | None = None, alert_current_a: float = 45.0) -> None:
        self._series_cells = 4
        self._r_shunt_ohm = 0.001
        self._max_expected_a = 60.0
        self._alert_current_a = alert_current_a
        self._keyframes: List[Dict[str, Any]] = []
        self._last_alarms = AlarmOutputState()
        if scenario_path is not None:
            self.load_scenario(scenario_path)

    @property
    def backend_name(self) -> str:
        return "wokwi"

    def initialize(self, series_cells: int, r_shunt_ohm: float = 0.001, max_expected_a: float = 60.0) -> None:
        if not 1 <= series_cells <= 6:
            raise ValueError(f"series_cells must be 1..6, got {series_cells}")
        self._series_cells = series_cells
        self._r_shunt_ohm = r_shunt_ohm
        self._max_expected_a = max_expected_a

    def load_scenario(self, scenario_path: str | Path) -> Dict[str, Any]:
        path = Path(scenario_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        safety = data.get("safety_invariant", {})
        if not safety.get("monitor_only", False):
            raise RuntimeError("Scenario violates monitor_only safety invariant.")
        pack = data.get("pack_config", {})
        self.initialize(
            series_cells=int(pack.get("series_cells", 4)),
            r_shunt_ohm=float(pack.get("r_shunt_ohm", 0.001)),
            max_expected_a=float(pack.get("max_expected_a", 60.0)),
        )
        self._keyframes = sorted(data.get("keyframes", []), key=lambda k: float(k["t_s"]))
        return data

    def _interpolate_keyframe(self, timestamp_s: float) -> Dict[str, Any]:
        if not self._keyframes:
            return {
                "current_a": 0.0,
                "cell_voltages_v": [3.85] * self._series_cells,
                "ntc_temps_c": [25.0, 25.0, 25.0, 25.0],
            }
        if timestamp_s <= float(self._keyframes[0]["t_s"]):
            return self._keyframes[0]
        if timestamp_s >= float(self._keyframes[-1]["t_s"]):
            return self._keyframes[-1]

        for idx in range(len(self._keyframes) - 1):
            k0 = self._keyframes[idx]
            k1 = self._keyframes[idx + 1]
            t0, t1 = float(k0["t_s"]), float(k1["t_s"])
            if t0 <= timestamp_s <= t1:
                alpha = (timestamp_s - t0) / max(1e-9, t1 - t0)
                curr = float(k0["current_a"]) + alpha * (float(k1["current_a"]) - float(k0["current_a"]))
                cells = [
                    float(c0) + alpha * (float(c1) - float(c0))
                    for c0, c1 in zip(k0["cell_voltages_v"], k1["cell_voltages_v"])
                ]
                temps = [
                    float(n0) + alpha * (float(n1) - float(n0))
                    for n0, n1 in zip(k0["ntc_temps_c"], k1["ntc_temps_c"])
                ]
                return {"current_a": curr, "cell_voltages_v": cells, "ntc_temps_c": temps}
        return self._keyframes[-1]

    def read_ina226(self, timestamp_s: float) -> INA226Telemetry:
        kf = self._interpolate_keyframe(timestamp_s)
        bus_v = sum(kf["cell_voltages_v"][: self._series_cells])
        curr_a = float(kf["current_a"])
        shunt_mv = curr_a * self._r_shunt_ohm * 1000.0
        power_w = bus_v * curr_a
        alert = abs(curr_a) > self._alert_current_a
        return INA226Telemetry(
            bus_voltage_v=round(bus_v, 4),
            shunt_voltage_mv=round(shunt_mv, 4),
            current_a=round(curr_a, 4),
            power_w=round(power_w, 3),
            alert_active=alert,
            valid=True,
        )

    def read_ntc_channels(self, timestamp_s: float) -> NTCTelemetry:
        kf = self._interpolate_keyframe(timestamp_s)
        temps = [round(float(t), 3) for t in kf["ntc_temps_c"][:4]]
        res = [round(celsius_to_ntc_resistance(t), 2) for t in temps]
        return NTCTelemetry(
            temperatures_c=temps,
            resistances_ohm=res,
            sensor_faults=[False, False, False, False],
        )

    def read_cell_taps(self, timestamp_s: float) -> CellTapTelemetry:
        kf = self._interpolate_keyframe(timestamp_s)
        cells = [round(float(v), 4) for v in kf["cell_voltages_v"][: self._series_cells]]
        taps: List[float] = []
        running = 0.0
        for v in cells:
            running += v
            taps.append(round(running, 4))
        return CellTapTelemetry(
            series_cells=self._series_cells,
            tap_voltages_v=taps,
            cell_voltages_v=cells,
            mux_gnd_offset_mv=0.0,
            mux_vref_v=2.048,
            tap_fault=False,
            valid=True,
        )

    def write_alarm_outputs(self, outputs: AlarmOutputState) -> None:
        self._last_alarms = outputs

    @property
    def last_alarms(self) -> AlarmOutputState:
        return self._last_alarms
