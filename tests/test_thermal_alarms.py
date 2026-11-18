"""Unit tests for Steinhart-Hart NTC thermistors, dT/dt thermal runaway & alarms."""

import pytest

from backend.analytics import (
    AlarmThresholds,
    PackAnalyticsEngine,
    PackConfiguration,
    ThermalDerivativeTracker,
    ntc_voltage_to_resistance,
    steinhart_hart_celsius,
)
from backend.datasets import generate_dataset_frames


def test_steinhart_hart_thermistor_accuracy_and_faults():
    # At 25C, R_ntc = 10k -> V_adc = 3.3 * 10k / (10k + 10k) = 1.65V
    r25 = ntc_voltage_to_resistance(1.65, r_series_ohm=10000.0, v_ref_v=3.3)
    assert r25 == pytest.approx(10000.0, rel=1e-6)
    t25 = steinhart_hart_celsius(r25)
    assert t25 == pytest.approx(25.0, abs=0.05)

    # 50C benchmark (~3603 Ohm)
    t50 = steinhart_hart_celsius(3603.0)
    assert t50 == pytest.approx(50.0, abs=0.1)

    # Short-to-GND and open-wire faults
    r_short = ntc_voltage_to_resistance(0.005)
    assert r_short == 0.0
    assert steinhart_hart_celsius(r_short) is None

    r_open = ntc_voltage_to_resistance(3.295)
    assert r_open >= 1e8
    assert steinhart_hart_celsius(r_open) is None


def test_thermal_runaway_derivative_ols_slope():
    tracker = ThermalDerivativeTracker(window_size=12, num_channels=4)

    # Ramp +6.0 C/min (+0.1 C/s) on channel 1, noisy steady state on channel 0
    for sec in range(0, 15):
        slope_steady = tracker.push(0, 26.0 + (0.04 if sec % 2 == 0 else -0.04), float(sec))
        slope_ramp = tracker.push(1, 30.0 + 0.1 * sec, float(sec))

    assert abs(slope_steady) < 0.3
    assert slope_ramp == pytest.approx(6.0, abs=0.05)


def test_alarm_rules_cover_thermal_voltage_current_and_tap_faults():
    lim = AlarmThresholds(
        cell_ov_warn_v=4.21,
        cell_ov_crit_v=4.25,
        cell_uv_warn_v=3.00,
        cell_uv_crit_v=2.75,
        cell_delta_warn_mv=50.0,
        cell_delta_crit_mv=150.0,
        max_discharge_a=40.0,
        max_charge_a=12.0,
        temp_warn_c=50.0,
        temp_crit_c=60.0,
        dtdt_warn_c_per_min=2.0,
        dtdt_crit_c_per_min=5.0,
    )
    eng = PackAnalyticsEngine(PackConfiguration(series_cells=4, alarms=lim))

    # Build a 10s +7.2 C/min thermal runaway ramp + severe cell imbalance + overcurrent + HW alert
    for s in range(0, 10):
        t_hotspot = 52.0 + 0.12 * s  # 7.2 C/min -> triggers TEMP_WARN and THERMAL_RUNAWAY_CRIT
        snap = eng.step(
            timestamp_s=float(s),
            pack_voltage_v=14.6,
            current_a=42.0,  # > 40A OC_DISCHARGE
            cell_voltages_v=[3.80, 3.80, 3.60, 3.40],  # 400 mV imbalance -> CELL_DELTA_CRIT
            temps_c=[30.0, t_hotspot, 31.0, 29.0],
            ina_hw_alert=True,
        )

    codes = set(snap.alarm_codes)
    assert "TEMP_WARN" in codes
    assert "THERMAL_RUNAWAY_CRIT" in codes
    assert "CELL_DELTA_CRIT" in codes
    assert "OC_DISCHARGE" in codes
    assert "INA_HW_ALERT" in codes


def test_fault_replay_dataset_triggers_expected_faults():
    fault_bundle = generate_dataset_frames("4s_thermal_imbalance_fault")
    all_codes = {code for frame in fault_bundle["frames"] for code in frame["alarm_codes"]}
    assert "THERMAL_RUNAWAY_CRIT" in all_codes
    assert "CELL_DELTA_WARN" in all_codes or "CELL_DELTA_CRIT" in all_codes
    assert "HIGH_RDC" in all_codes
