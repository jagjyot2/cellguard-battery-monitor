"""Unit tests for 21700 OCV+Coulomb SoC fusion, R_dc estimator, and SoH tracking."""

import pytest

from backend.analytics import (
    PackAnalyticsEngine,
    PackConfiguration,
    ocv_to_soc_percent,
    soc_to_ocv_voltage,
)
from backend.datasets import generate_dataset_frames


def test_21700_ocv_lut_monotonic_and_roundtrip():
    assert ocv_to_soc_percent(2.30) == 0.0
    assert ocv_to_soc_percent(4.25) == 100.0

    prev_soc = -1.0
    for mv in range(2500, 4210, 50):
        v = mv / 1000.0
        soc = ocv_to_soc_percent(v)
        assert soc >= prev_soc
        prev_soc = soc
        v_back = soc_to_ocv_voltage(soc)
        assert v_back == pytest.approx(v, abs=1e-6)


def test_coulomb_counting_accuracy_under_constant_load():
    cfg = PackConfiguration(series_cells=4, nominal_capacity_mah=5000.0, r_dc_nominal_cell_mohm=22.0)
    eng = PackAnalyticsEngine(cfg)

    # Start at 4.20V/cell (100% SoC) and discharge 5.0 A for 1800 s (0.5 h = 2500 mAh = 50% SoC)
    v_pack_0 = 4.20 * 4
    eng.step(0.0, v_pack_0, 0.0, [4.20] * 4, [25.0] * 4)

    for sec in range(1, 1801):
        # Simulate slight voltage drop under 5A load
        v_c = 3.85 - 5.0 * 0.022
        snap = eng.step(float(sec), v_c * 4, 5.0, [v_c] * 4, [26.0] * 4)

    # 1s ramp at t=0..1s averages 2.5A (0.694 mAh) + 1799s @ 5.0A (2498.6 mAh) ≈ 2499.3 mAh
    assert snap.mah_discharged == pytest.approx(2499.3, abs=2.0)
    assert snap.soc_percent == pytest.approx(50.0, abs=0.25)
    assert snap.wh_discharged > 35.0


def test_ocv_fusion_converges_during_rest():
    cfg = PackConfiguration(series_cells=4, nominal_capacity_mah=5000.0, r_dc_nominal_cell_mohm=22.0)
    eng = PackAnalyticsEngine(cfg)
    # Initialize at 4.00V (89% SoC) then force artificial drift in coulomb counter
    eng.step(0.0, 16.0, 0.0, [4.00] * 4, [25.0] * 4)
    eng.soc_percent = 65.0  # Simulate drifted state

    # Rest for 90s at true 3.84V OCV (74% SoC)
    for t in range(1, 91):
        snap = eng.step(float(t), 3.84 * 4, 0.02, [3.84] * 4, [25.0] * 4)

    # Complementary OCV fusion should pull drifted 65% sharply toward 74%
    assert snap.soc_percent > 72.5
    assert snap.soc_ocv_est_percent == pytest.approx(74.0, abs=0.2)


def test_dynamic_rdc_load_step_estimator_and_soh_fade():
    cfg = PackConfiguration(series_cells=4, nominal_capacity_mah=5000.0, r_dc_nominal_cell_mohm=22.0)
    eng = PackAnalyticsEngine(cfg)

    true_cell_r_ohm = 0.036  # Aged 36 mOhm/cell -> 144 mOhm pack
    ocv = 3.92
    # Steady low load at 2A
    for t in [0.0, 1.0, 2.0]:
        v_c = ocv - 2.0 * true_cell_r_ohm
        eng.step(t, v_c * 4, 2.0, [v_c] * 4, [28.0] * 4)

    # Sharp 2A -> 22A step (+20A) within 1 second -> dV = -20 * 0.144 = -2.88V
    v_c_step = ocv - 22.0 * true_cell_r_ohm
    snap = eng.step(3.0, v_c_step * 4, 22.0, [v_c_step] * 4, [28.0] * 4)

    assert snap.rdc_step_count == 1
    assert snap.r_dc_cell_mohm == pytest.approx(36.0, abs=0.5)
    # R_dc = 36 / 22 = 1.636x -> soh_resistance = 100 - 20*(0.636) ≈ 87.27%
    assert snap.soh_resistance_percent == pytest.approx(87.27, abs=0.5)
    assert snap.soh_percent < 97.0


def test_dataset_replay_generators_produce_valid_physics():
    b4 = generate_dataset_frames("4s_50e_nominal")
    assert b4["dataset"]["series_cells"] == 4
    assert len(b4["frames"]) > 80
    assert b4["frames"][-1]["mah_discharged"] > 2000.0
    assert b4["frames"][-1]["rdc_step_count"] >= 2

    b6 = generate_dataset_frames("6s_p42a_loadsteps")
    assert b6["dataset"]["series_cells"] == 6
    assert len(b6["frames"][0]["cell_voltages_v"]) == 6
    assert b6["frames"][-1]["rdc_step_count"] >= 3
