"""Synthetic & Bench 21700 Li-Ion Discharge Replay Datasets.

Generates physically realistic 4S (14.8V) and 6S (22.2V) 21700 NMC/INR telemetry
sequences driven by the exact CellGuard OCV curve and ohmic IR sag model,
including rapid load steps for dynamic R_dc verification and thermal anomaly replay.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.analytics import (
    PackAnalyticsEngine,
    PackConfiguration,
    soc_to_ocv_voltage,
)

DATASET_CATALOG: Dict[str, Dict[str, Any]] = {
    "4s_50e_nominal": {
        "id": "4s_50e_nominal",
        "title": "4S 21700 Samsung 50E Nominal Discharge (14.8V / 5000mAh)",
        "series_cells": 4,
        "nominal_capacity_mah": 5000.0,
        "r_dc_nominal_cell_mohm": 22.0,
        "description": "Healthy 4S1P 21700 pack with 2A->12A load steps and gradual thermal rise.",
    },
    "6s_p42a_loadsteps": {
        "id": "6s_p42a_loadsteps",
        "title": "6S 21700 Molicel P42A High-Drain Load Steps (22.2V / 4200mAh)",
        "series_cells": 6,
        "nominal_capacity_mah": 4200.0,
        "r_dc_nominal_cell_mohm": 15.0,
        "description": "6S1P high-power pack under pulsed 5A/25A/0A load steps with rest OCV convergence.",
    },
    "4s_thermal_imbalance_fault": {
        "id": "4s_thermal_imbalance_fault",
        "title": "4S Aged Pack: Cell Drift + Thermal Runaway Derivative Test",
        "series_cells": 4,
        "nominal_capacity_mah": 4800.0,
        "r_dc_nominal_cell_mohm": 22.0,
        "description": "Bench fault replay showing elevated R_dc, weak Cell 3 imbalance, and >5 C/min dT/dt ramp.",
    },
}


def generate_dataset_frames(dataset_id: str) -> Dict[str, Any]:
    """Build raw sensor frames and run them through PackAnalyticsEngine."""
    if dataset_id not in DATASET_CATALOG:
        raise ValueError(f"Unknown dataset_id: {dataset_id}")

    meta = DATASET_CATALOG[dataset_id]
    n_cells = int(meta["series_cells"])
    cap_mah = float(meta["nominal_capacity_mah"])
    r_nom_mohm = float(meta["r_dc_nominal_cell_mohm"])

    cfg = PackConfiguration(
        series_cells=n_cells,
        nominal_capacity_mah=cap_mah,
        r_shunt_ohm=0.001,
        max_expected_a=60.0,
        r_dc_nominal_cell_mohm=r_nom_mohm,
    )
    engine = PackAnalyticsEngine(cfg)

    frames: List[Dict[str, Any]] = []

    if dataset_id == "4s_50e_nominal":
        # 15s grid plus explicit 1s step capture edges at t=100, 300, 700, 1200
        base = set(range(0, 1501, 15))
        base.update({99, 100, 299, 300, 699, 700, 1199, 1200})
        timestamps: List[float] = [float(x) for x in sorted(base)]

        cell_r_mohm = [21.5, 22.0, 22.4, 21.8]
        cell_cap_scale = [1.00, 0.995, 0.990, 1.002]
        true_mah_used = 0.0
        prev_t = 0.0
        prev_i = 0.5

        for ts in timestamps:
            if ts < 100.0:
                current_a = 1.5
            elif ts < 300.0:
                current_a = 12.0
            elif ts < 700.0:
                current_a = 6.5
            elif ts < 1200.0:
                current_a = 14.0
            else:
                current_a = 0.05  # Rest window at end

            dt_s = max(0.0, ts - prev_t)
            if dt_s > 0.0:
                true_mah_used += 0.5 * (prev_i + current_a) * (dt_s / 3600.0) * 1000.0
            prev_t = ts
            prev_i = current_a

            cells_v: List[float] = []
            for idx in range(n_cells):
                c_soc = max(2.0, 98.0 - (true_mah_used / (cap_mah * cell_cap_scale[idx])) * 100.0)
                v_c = soc_to_ocv_voltage(c_soc) - current_a * (cell_r_mohm[idx] / 1000.0)
                cells_v.append(round(v_c, 4))

            pack_v = round(sum(cells_v), 4)
            t_rise = min(11.5, (ts / 1500.0) * 11.0)
            temps_c = [
                round(25.0 + t_rise, 2),
                round(25.4 + t_rise * 1.04, 2),
                round(24.6 + t_rise * 0.78, 2),
                round(24.2 + t_rise * 0.55, 2),
            ]
            snap = engine.step(ts, pack_v, current_a, cells_v, temps_c, ina_hw_alert=False)
            frames.append(_snapshot_to_dict(snap))

    elif dataset_id == "6s_p42a_loadsteps":
        base = set(range(0, 1081, 12))
        base.update({59, 60, 239, 240, 419, 420, 599, 600, 899, 900})
        timestamps = [float(x) for x in sorted(base)]

        cell_r_mohm = [14.8, 15.2, 15.0, 15.5, 14.9, 15.1]
        true_mah_used = 0.0
        prev_t = 0.0
        prev_i = 2.0

        for ts in timestamps:
            if ts < 60.0:
                current_a = 2.0
            elif ts < 240.0:
                current_a = 24.0
            elif ts < 420.0:
                current_a = 8.0
            elif ts < 600.0:
                current_a = 26.0
            elif ts < 900.0:
                current_a = 12.0
            else:
                current_a = 0.04  # Rest OCV convergence tail

            dt_s = max(0.0, ts - prev_t)
            if dt_s > 0.0:
                true_mah_used += 0.5 * (prev_i + current_a) * (dt_s / 3600.0) * 1000.0
            prev_t = ts
            prev_i = current_a

            cells_v = []
            for idx in range(n_cells):
                c_soc = max(3.0, 99.0 - (true_mah_used / cap_mah) * 100.0 - idx * 0.15)
                v_c = soc_to_ocv_voltage(c_soc) - current_a * (cell_r_mohm[idx] / 1000.0)
                cells_v.append(round(v_c, 4))

            pack_v = round(sum(cells_v), 4)
            t_rise = min(17.0, (ts / 900.0) * 16.5) if ts < 900 else 16.5 - (ts - 900) * 0.015
            temps_c = [
                round(26.0 + t_rise, 2),
                round(26.5 + t_rise * 1.05, 2),
                round(25.2 + t_rise * 0.85, 2),
                round(24.5 + t_rise * 0.65, 2),
            ]
            snap = engine.step(ts, pack_v, current_a, cells_v, temps_c, ina_hw_alert=False)
            frames.append(_snapshot_to_dict(snap))

    else:  # "4s_thermal_imbalance_fault"
        # 1s-2s resolution thermal ramp & high R_dc cell drift test
        timestamps = [float(k * 2) for k in range(0, 121)]  # 0..240s
        cell_r_mohm = [36.0, 38.0, 48.0, 37.0]
        true_mah_used = 1200.0  # Start mid-discharge (~75% SoC)
        prev_t = 0.0
        prev_i = 2.0

        for ts in timestamps:
            if ts < 20.0:
                current_a = 2.0
            elif ts < 160.0:
                current_a = 18.0
            else:
                current_a = 4.0

            dt_s = max(0.0, ts - prev_t)
            if dt_s > 0.0:
                true_mah_used += 0.5 * (prev_i + current_a) * (dt_s / 3600.0) * 1000.0
            prev_t = ts
            prev_i = current_a

            cells_v = []
            for idx in range(n_cells):
                # Cell 2 (index 2) is aged/imbalanced (~9% lower SoC & higher R_dc)
                soc_offset = 9.5 if idx == 2 else 0.0
                c_soc = max(2.0, 95.0 - soc_offset - (true_mah_used / cap_mah) * 100.0)
                v_c = soc_to_ocv_voltage(c_soc) - current_a * (cell_r_mohm[idx] / 1000.0)
                cells_v.append(round(v_c, 4))

            pack_v = round(sum(cells_v), 4)
            # Trigger thermal runaway slope after t=120s (~6.8 C/min)
            if ts < 120.0:
                t_hotspot = 30.0 + (ts / 120.0) * 4.0
            else:
                t_hotspot = 34.0 + ((ts - 120.0) / 60.0) * 10.5  # >10 C/min runaway ramp!
            temps_c = [
                round(29.0 + (ts / 240.0) * 5.0, 2),
                round(t_hotspot, 2),
                round(28.5 + (ts / 240.0) * 4.0, 2),
                round(26.0 + (ts / 240.0) * 2.0, 2),
            ]
            snap = engine.step(ts, pack_v, current_a, cells_v, temps_c, ina_hw_alert=False)
            frames.append(_snapshot_to_dict(snap))

    return {
        "dataset": meta,
        "config": cfg,
        "frames": frames,
    }


def _snapshot_to_dict(snap: Any) -> Dict[str, Any]:
    return {
        "timestamp_s": round(snap.timestamp_s, 3),
        "series_cells": snap.series_cells,
        "pack_voltage_v": round(snap.pack_voltage_v, 4),
        "current_a": round(snap.current_a, 4),
        "power_w": round(snap.power_w, 3),
        "cell_voltages_v": [round(v, 4) for v in snap.cell_voltages_v],
        "cell_min_v": round(snap.cell_min_v, 4),
        "cell_max_v": round(snap.cell_max_v, 4),
        "cell_delta_mv": round(snap.cell_delta_mv, 2),
        "temps_c": [round(t, 2) for t in snap.temps_c],
        "dtdt_c_per_min": [round(d, 3) for d in snap.dtdt_c_per_min],
        "temp_max_c": round(snap.temp_max_c, 2),
        "dtdt_max_c_per_min": round(snap.dtdt_max_c_per_min, 3),
        "soc_percent": round(snap.soc_percent, 2),
        "soc_ocv_est_percent": round(snap.soc_ocv_est_percent, 2),
        "soh_percent": round(snap.soh_percent, 2),
        "soh_capacity_percent": round(snap.soh_capacity_percent, 2),
        "soh_resistance_percent": round(snap.soh_resistance_percent, 2),
        "mah_discharged": round(snap.mah_discharged, 2),
        "mah_charged": round(snap.mah_charged, 2),
        "wh_discharged": round(snap.wh_discharged, 3),
        "wh_charged": round(snap.wh_charged, 3),
        "r_dc_pack_ohm": round(snap.r_dc_pack_ohm, 5),
        "r_dc_cell_mohm": round(snap.r_dc_cell_mohm, 2),
        "ocv_est_cell_v": round(snap.ocv_est_cell_v, 4),
        "rest_seconds": round(snap.rest_seconds, 1),
        "rdc_step_count": snap.rdc_step_count,
        "alarms": [
            {"code": a.code, "severity": a.severity, "message": a.message}
            for a in snap.alarms
        ],
        "alarm_codes": list(snap.alarm_codes),
    }
