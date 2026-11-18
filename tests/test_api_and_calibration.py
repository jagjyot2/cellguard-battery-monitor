"""Integration tests for FastAPI REST endpoints, SQLite persistence, and calibration CLI."""

from fastapi.testclient import TestClient
import pytest

from backend.main import create_app
from calibration_cli import main as cal_cli_main


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "cellguard_test.db"
    app = create_app(db_path=str(db_file))
    with TestClient(app) as tc:
        yield tc


def test_health_and_dashboard_root(client: TestClient):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["safety"]["monitor_only"] is True
    assert body["safety"]["balancing_supported"] is False
    assert body["safety"]["charging_supported"] is False
    assert body["safety"]["fet_switching_supported"] is False
    assert body["safety"]["requires_external_bms_and_fuse"] is True

    root = client.get("/")
    assert root.status_code == 200
    assert "text/html" in root.headers["content-type"]
    assert "CellGuard" in root.text


def test_dataset_replay_history_and_csv_export(client: TestClient):
    replay = client.post("/api/sessions/replay", json={"dataset_id": "6s_p42a_loadsteps"})
    assert replay.status_code == 200
    assert replay.json()["session_id"] == "6s_p42a_loadsteps"
    assert replay.json()["sample_count"] > 50

    latest = client.get("/api/telemetry/latest")
    assert latest.status_code == 200
    assert latest.json()["sample"]["series_cells"] == 6

    hist = client.get("/api/telemetry/history?session_id=6s_p42a_loadsteps")
    assert hist.status_code == 200
    assert hist.json()["count"] == replay.json()["sample_count"]

    csv_res = client.get("/api/export/csv?session_id=6s_p42a_loadsteps")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    lines = csv_res.text.strip().splitlines()
    assert lines[0].startswith("timestamp_s,pack_voltage_v,current_a")
    assert len(lines) == replay.json()["sample_count"] + 1


def test_live_ingest_thresholds_and_alarm_ack(client: TestClient):
    # Tighten temp threshold to trigger alarm on ingest
    thr_res = client.put(
        "/api/thresholds",
        json={
            "cell_ov_warn_v": 4.21,
            "cell_ov_crit_v": 4.25,
            "cell_uv_warn_v": 3.00,
            "cell_uv_crit_v": 2.75,
            "cell_delta_warn_mv": 40.0,
            "cell_delta_crit_mv": 120.0,
            "max_discharge_a": 45.0,
            "max_charge_a": 15.0,
            "temp_warn_c": 45.0,
            "temp_crit_c": 55.0,
            "dtdt_warn_c_per_min": 2.0,
            "dtdt_crit_c_per_min": 5.0,
            "rdc_ratio_warn": 1.75,
            "tap_mismatch_max_v": 0.35,
        },
    )
    assert thr_res.status_code == 200

    ingest = client.post(
        "/api/telemetry/ingest",
        json={
            "session_id": "bench-smoke",
            "timestamp_s": 1.0,
            "pack_voltage_v": 15.20,
            "current_a": 8.0,
            "cell_voltages_v": [3.85, 3.84, 3.83, 3.68],  # 170 mV delta -> CRIT
            "temps_c": [47.0, 32.0, 30.0, 26.0],  # 47C >= 45C warn
            "ina_hw_alert": False,
        },
    )
    assert ingest.status_code == 200
    codes = ingest.json()["sample"]["alarm_codes"]
    assert "CELL_DELTA_CRIT" in codes
    assert "TEMP_WARN" in codes

    alarms = client.get("/api/alarms?session_id=bench-smoke")
    assert alarms.status_code == 200
    assert len(alarms.json()["alarms"]) >= 2

    ack = client.post("/api/alarms/ack?session_id=bench-smoke")
    assert ack.status_code == 200
    assert ack.json()["acknowledged_count"] >= 2


def test_calibration_calculator_endpoint_and_cli(client: TestClient, capsys):
    calc = client.post(
        "/api/calibration/calculate",
        json={
            "r_shunt_mohm": 1.0,
            "max_expected_current_a": 60.0,
            "series_cells": 4,
            "nominal_capacity_mah": 5000.0,
            "current_meas1": 0.05,
            "current_ref1": 0.0,
            "current_meas2": 20.05,
            "current_ref2": 20.0,
            "vbus_meas1": 12.0,
            "vbus_ref1": 12.0,
            "vbus_meas2": 16.8,
            "vbus_ref2": 16.8,
            "tap_channel": 2,
            "tap_meas1": 6.0,
            "tap_ref1": 6.06,
            "tap_meas2": 8.4,
            "tap_ref2": 8.484,
        },
    )
    assert calc.status_code == 200
    data = calc.json()
    assert data["ina226"]["cal_register"] == 2796
    assert data["current_calibration"]["gain"] == pytest.approx(1.0, abs=1e-5)
    assert data["current_calibration"]["offset_a"] == pytest.approx(-0.05, abs=1e-5)
    assert data["tap_calibration"]["gain"] == pytest.approx(1.01, abs=1e-4)
    assert any(cmd.startswith("SET_TAP_CAL 2") for cmd in data["esp32_cli_commands"])

    # Degenerate two-point calibration must return HTTP 400
    bad = client.post(
        "/api/calibration/calculate",
        json={
            "current_meas1": 5.0,
            "current_ref1": 5.0,
            "current_meas2": 5.0,
            "current_ref2": 10.0,
        },
    )
    assert bad.status_code == 400

    # Verify CLI utility executes cleanly
    rc = cal_cli_main([
        "--series-cells", "6",
        "--capacity-mah", "4200",
        "--shunt-mohm", "1.0",
        "--max-current", "60",
        "--curr-meas1", "0.0", "--curr-ref1", "0.0",
        "--curr-meas2", "19.8", "--curr-ref2", "20.0",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert '"cal_register": 2796' in captured.out
