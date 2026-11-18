"""CellGuard FastAPI Analytics Backend & Dashboard Server.

Serves the interactive dark-mode React+TS dashboard at `/`, provides REST API
endpoints for real-time/historical 21700 discharge analytics, alarm rule
configuration, interactive INA226 & voltage-divider calibration, dataset
replay, and CSV export.
"""

from __future__ import annotations

import csv
import io
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.analytics import (
    BALANCING_SUPPORTED,
    CHARGING_SUPPORTED,
    DEFAULT_DIVIDER_RATIOS,
    FET_SWITCHING_SUPPORTED,
    MONITOR_ONLY,
    AlarmThresholds,
    PackAnalyticsEngine,
    PackConfiguration,
    compute_ina226_calibration_params,
    compute_two_point_calibration,
)
from backend.database import CellGuardDatabase
from backend.datasets import DATASET_CATALOG, _snapshot_to_dict, generate_dataset_frames

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


# ==============================================================================
# Pydantic V2 Request / Response Contracts
# ==============================================================================

class ThresholdsPayload(BaseModel):
    cell_ov_warn_v: float = Field(4.21, ge=3.5, le=4.4)
    cell_ov_crit_v: float = Field(4.25, ge=3.6, le=4.5)
    cell_uv_warn_v: float = Field(3.00, ge=2.0, le=3.6)
    cell_uv_crit_v: float = Field(2.75, ge=2.0, le=3.5)
    cell_delta_warn_mv: float = Field(50.0, ge=5.0, le=500.0)
    cell_delta_crit_mv: float = Field(150.0, ge=10.0, le=1000.0)
    max_discharge_a: float = Field(45.0, ge=1.0, le=200.0)
    max_charge_a: float = Field(15.0, ge=0.5, le=100.0)
    temp_warn_c: float = Field(50.0, ge=25.0, le=90.0)
    temp_crit_c: float = Field(60.0, ge=30.0, le=100.0)
    dtdt_warn_c_per_min: float = Field(2.0, ge=0.2, le=20.0)
    dtdt_crit_c_per_min: float = Field(5.0, ge=0.5, le=30.0)
    rdc_ratio_warn: float = Field(1.75, ge=1.1, le=5.0)
    tap_mismatch_max_v: float = Field(0.35, ge=0.05, le=2.0)


class TelemetryIngestPayload(BaseModel):
    session_id: str = "live-bench"
    timestamp_s: float = Field(..., ge=0.0)
    pack_voltage_v: float = Field(..., ge=0.0, le=40.0)
    current_a: float = Field(..., ge=-150.0, le=150.0)
    cell_voltages_v: Optional[List[float]] = None
    temps_c: Optional[List[float]] = None
    ina_hw_alert: bool = False


class CalibrationCalculatePayload(BaseModel):
    r_shunt_mohm: float = Field(1.0, gt=0.05, le=100.0)
    max_expected_current_a: float = Field(60.0, gt=1.0, le=250.0)
    series_cells: int = Field(4, ge=1, le=6)
    nominal_capacity_mah: float = Field(5000.0, ge=200.0, le=50000.0)
    current_meas1: float = 0.0
    current_ref1: float = 0.0
    current_meas2: float = 10.0
    current_ref2: float = 10.0
    vbus_meas1: float = 12.0
    vbus_ref1: float = 12.0
    vbus_meas2: float = 16.8
    vbus_ref2: float = 16.8
    tap_channel: int = Field(1, ge=1, le=6)
    tap_meas1: float = 3.0
    tap_ref1: float = 3.0
    tap_meas2: float = 4.2
    tap_ref2: float = 4.2


class CalibrationProfilePayload(BaseModel):
    series_cells: int = Field(4, ge=1, le=6)
    nominal_capacity_mah: float = Field(5000.0, ge=200.0, le=50000.0)
    r_shunt_mohm: float = Field(1.0, gt=0.05, le=100.0)
    max_expected_current_a: float = Field(60.0, gt=1.0, le=250.0)
    current_gain: float = 1.0
    current_offset_a: float = 0.0
    vbus_gain: float = 1.0
    vbus_offset_v: float = 0.0
    tap_gains: List[float] = Field(default_factory=lambda: [1.0] * 6)
    tap_offsets_v: List[float] = Field(default_factory=lambda: [0.0] * 6)


class ReplayRequest(BaseModel):
    dataset_id: str = "4s_50e_nominal"


# ==============================================================================
# Application Runtime State Container
# ==============================================================================

class AppState:
    def __init__(self, db_path: str) -> None:
        self.db = CellGuardDatabase(db_path=db_path)
        self.active_session_id = "4s_50e_nominal"
        self.thresholds = AlarmThresholds()
        self.engine = PackAnalyticsEngine(PackConfiguration(alarms=self.thresholds))
        self._load_or_seed()

    def _load_or_seed(self) -> None:
        saved_thresh = self.db.load_kv("alarm_thresholds")
        if saved_thresh:
            self.thresholds = AlarmThresholds(**saved_thresh)
            self.engine.update_thresholds(self.thresholds)

        saved_cal = self.db.load_kv("calibration_profile")
        if not saved_cal:
            self.db.save_kv("calibration_profile", CalibrationProfilePayload().model_dump())

        if not self.db.list_sessions():
            self.load_dataset("4s_50e_nominal")
        else:
            sessions = self.db.list_sessions()
            self.active_session_id = sessions[0]["session_id"]

    def load_dataset(self, dataset_id: str) -> Dict[str, Any]:
        bundle = generate_dataset_frames(dataset_id)
        meta = bundle["dataset"]
        cfg: PackConfiguration = bundle["config"]
        self.db.create_session(
            session_id=dataset_id,
            title=meta["title"],
            series_cells=cfg.series_cells,
            nominal_capacity_mah=cfg.nominal_capacity_mah,
            r_dc_nominal_cell_mohm=cfg.r_dc_nominal_cell_mohm,
            dataset_id=dataset_id,
        )
        self.db.clear_session_samples(dataset_id)
        self.db.insert_frames_batch(dataset_id, bundle["frames"])
        self.active_session_id = dataset_id
        self.engine = PackAnalyticsEngine(
            PackConfiguration(
                series_cells=cfg.series_cells,
                nominal_capacity_mah=cfg.nominal_capacity_mah,
                r_shunt_ohm=cfg.r_shunt_ohm,
                max_expected_a=cfg.max_expected_a,
                r_dc_nominal_cell_mohm=cfg.r_dc_nominal_cell_mohm,
                alarms=self.thresholds,
            )
        )
        return {
            "session_id": dataset_id,
            "title": meta["title"],
            "sample_count": len(bundle["frames"]),
        }


def create_app(db_path: Optional[str] = None) -> FastAPI:
    resolved_db = db_path or os.getenv("CELLGUARD_DB_PATH", "./cellguard_telemetry.db")
    runtime = AppState(db_path=resolved_db)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield

    app = FastAPI(
        title="CellGuard Battery Telemetry & Health Analytics API",
        version="1.0.0",
        description=(
            "Non-invasive 21700 Li-Ion pack monitoring and health analytics platform "
            "used alongside an external commercial BMS and inline main fuse."
        ),
        lifespan=lifespan,
    )
    app.state.runtime = runtime

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Health & Safety Invariant Endpoint ---
    @app.get("/api/health")
    def health_check() -> Dict[str, Any]:
        return {
            "status": "ok",
            "service": "cellguard-battery-monitor",
            "version": "1.0.0",
            "active_session_id": runtime.active_session_id,
            "safety": {
                "monitor_only": MONITOR_ONLY,
                "balancing_supported": BALANCING_SUPPORTED,
                "charging_supported": CHARGING_SUPPORTED,
                "fet_switching_supported": FET_SWITCHING_SUPPORTED,
                "requires_external_bms_and_fuse": True,
            },
        }

    # --- Sessions & Bench Dataset Replay ---
    @app.get("/api/sessions")
    def list_sessions() -> Dict[str, Any]:
        return {
            "active_session_id": runtime.active_session_id,
            "sessions": runtime.db.list_sessions(),
            "datasets": list(DATASET_CATALOG.values()),
        }

    @app.post("/api/sessions/replay")
    def replay_dataset(req: ReplayRequest) -> Dict[str, Any]:
        if req.dataset_id not in DATASET_CATALOG:
            raise HTTPException(status_code=404, detail=f"Unknown dataset_id '{req.dataset_id}'")
        return runtime.load_dataset(req.dataset_id)

    # --- Telemetry Query & Ingestion ---
    @app.get("/api/telemetry/latest")
    def get_latest_telemetry(session_id: Optional[str] = None) -> Dict[str, Any]:
        sid = session_id or runtime.active_session_id
        latest = runtime.db.get_latest_sample(sid)
        if not latest:
            raise HTTPException(status_code=404, detail=f"No telemetry found for session '{sid}'")
        session_meta = runtime.db.get_session(sid)
        return {
            "session": session_meta,
            "sample": latest,
        }

    @app.get("/api/telemetry/history")
    def get_telemetry_history(
        session_id: Optional[str] = None,
        limit: int = Query(1000, ge=1, le=10000),
    ) -> Dict[str, Any]:
        sid = session_id or runtime.active_session_id
        history = runtime.db.get_history(sid, limit=limit)
        session_meta = runtime.db.get_session(sid)
        return {
            "session_id": sid,
            "session": session_meta,
            "count": len(history),
            "samples": history,
        }

    @app.post("/api/telemetry/ingest")
    def ingest_telemetry(payload: TelemetryIngestPayload) -> Dict[str, Any]:
        sid = payload.session_id
        existing = runtime.db.get_session(sid)
        if not existing:
            n_cells = len(payload.cell_voltages_v) if payload.cell_voltages_v else runtime.engine.cfg.series_cells
            runtime.engine = PackAnalyticsEngine(
                PackConfiguration(
                    series_cells=n_cells,
                    nominal_capacity_mah=runtime.engine.cfg.nominal_capacity_mah,
                    r_shunt_ohm=runtime.engine.cfg.r_shunt_ohm,
                    max_expected_a=runtime.engine.cfg.max_expected_a,
                    r_dc_nominal_cell_mohm=runtime.engine.cfg.r_dc_nominal_cell_mohm,
                    alarms=runtime.thresholds,
                )
            )
            runtime.db.create_session(
                session_id=sid,
                title=f"Live Telemetry Session ({sid})",
                series_cells=n_cells,
                nominal_capacity_mah=runtime.engine.cfg.nominal_capacity_mah,
                r_dc_nominal_cell_mohm=runtime.engine.cfg.r_dc_nominal_cell_mohm,
            )
        runtime.active_session_id = sid
        snap = runtime.engine.step(
            timestamp_s=payload.timestamp_s,
            pack_voltage_v=payload.pack_voltage_v,
            current_a=payload.current_a,
            cell_voltages_v=payload.cell_voltages_v,
            temps_c=payload.temps_c,
            ina_hw_alert=payload.ina_hw_alert,
        )
        frame = _snapshot_to_dict(snap)
        runtime.db.insert_single_frame(sid, frame)
        return {"status": "ingested", "session_id": sid, "sample": frame}

    # --- Alarms & Configurable Thresholds ---
    @app.get("/api/alarms")
    def list_alarms(session_id: Optional[str] = None, limit: int = Query(200, ge=1, le=2000)) -> Dict[str, Any]:
        sid = session_id or runtime.active_session_id
        return {
            "session_id": sid,
            "alarms": runtime.db.get_alarms(sid, limit=limit),
        }

    @app.post("/api/alarms/ack")
    def acknowledge_alarms(session_id: Optional[str] = None) -> Dict[str, Any]:
        count = runtime.db.acknowledge_alarms(session_id)
        return {"acknowledged_count": count}

    @app.get("/api/thresholds")
    def get_thresholds() -> Dict[str, Any]:
        return runtime.thresholds.__dict__

    @app.put("/api/thresholds")
    def update_thresholds(payload: ThresholdsPayload) -> Dict[str, Any]:
        runtime.thresholds = AlarmThresholds(**payload.model_dump())
        runtime.engine.update_thresholds(runtime.thresholds)
        runtime.db.save_kv("alarm_thresholds", payload.model_dump())
        return {"status": "updated", "thresholds": payload.model_dump()}

    # --- Interactive Calibration Calculator & Active Profile ---
    @app.get("/api/calibration")
    def get_calibration() -> Dict[str, Any]:
        cal = runtime.db.load_kv("calibration_profile") or CalibrationProfilePayload().model_dump()
        ina_params = compute_ina226_calibration_params(
            r_shunt_ohm=float(cal["r_shunt_mohm"]) / 1000.0,
            max_expected_current_a=float(cal["max_expected_current_a"]),
        )
        return {
            "profile": cal,
            "ina226_math": ina_params,
            "divider_ratios": list(DEFAULT_DIVIDER_RATIOS),
        }

    @app.put("/api/calibration")
    def save_calibration(payload: CalibrationProfilePayload) -> Dict[str, Any]:
        data = payload.model_dump()
        runtime.db.save_kv("calibration_profile", data)
        ina_params = compute_ina226_calibration_params(
            r_shunt_ohm=payload.r_shunt_mohm / 1000.0,
            max_expected_current_a=payload.max_expected_current_a,
        )
        return {"status": "saved", "profile": data, "ina226_math": ina_params}

    @app.post("/api/calibration/calculate")
    def calculate_calibration(payload: CalibrationCalculatePayload) -> Dict[str, Any]:
        try:
            curr_gain, curr_off = compute_two_point_calibration(
                payload.current_meas1, payload.current_ref1,
                payload.current_meas2, payload.current_ref2,
            )
            vbus_gain, vbus_off = compute_two_point_calibration(
                payload.vbus_meas1, payload.vbus_ref1,
                payload.vbus_meas2, payload.vbus_ref2,
            )
            tap_gain, tap_off = compute_two_point_calibration(
                payload.tap_meas1, payload.tap_ref1,
                payload.tap_meas2, payload.tap_ref2,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        ina_params = compute_ina226_calibration_params(
            r_shunt_ohm=payload.r_shunt_mohm / 1000.0,
            max_expected_current_a=payload.max_expected_current_a,
        )
        cli_commands = [
            f"SET_PACK {payload.series_cells} {payload.nominal_capacity_mah:.1f} {payload.r_shunt_mohm:.4f}",
            f"SET_TAP_CAL {payload.tap_channel} {tap_gain:.6f} {tap_off:.6f}",
            "SAVE",
        ]
        return {
            "ina226": ina_params,
            "current_calibration": {"gain": round(curr_gain, 6), "offset_a": round(curr_off, 6)},
            "vbus_calibration": {"gain": round(vbus_gain, 6), "offset_v": round(vbus_off, 6)},
            "tap_calibration": {
                "channel": payload.tap_channel,
                "divider_ratio": DEFAULT_DIVIDER_RATIOS[payload.tap_channel - 1],
                "gain": round(tap_gain, 6),
                "offset_v": round(tap_off, 6),
            },
            "esp32_cli_commands": cli_commands,
        }

    # --- CSV Telemetry History Export ---
    @app.get("/api/export/csv")
    def export_csv(session_id: Optional[str] = None) -> StreamingResponse:
        sid = session_id or runtime.active_session_id
        rows = runtime.db.get_history(sid, limit=10000)
        if not rows:
            raise HTTPException(status_code=404, detail=f"No samples available for session '{sid}'")

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "timestamp_s", "pack_voltage_v", "current_a", "power_w",
            "soc_percent", "soc_ocv_est_percent", "soh_percent",
            "mah_discharged", "wh_discharged", "r_dc_pack_ohm", "r_dc_cell_mohm",
            "cell_min_v", "cell_max_v", "cell_delta_mv",
            "temp_max_c", "dtdt_max_c_per_min",
            "cells_v", "temps_c", "alarms",
        ])
        for r in rows:
            writer.writerow([
                r["timestamp_s"],
                r["pack_voltage_v"],
                r["current_a"],
                r["power_w"],
                r["soc_percent"],
                r["soc_ocv_est_percent"],
                r["soh_percent"],
                r["mah_discharged"],
                r["wh_discharged"],
                r["r_dc_pack_ohm"],
                r["r_dc_cell_mohm"],
                r["cell_min_v"],
                r["cell_max_v"],
                r["cell_delta_mv"],
                r["temp_max_c"],
                r["dtdt_max_c_per_min"],
                "|".join(f"{v:.4f}" for v in r["cell_voltages_v"]),
                "|".join(f"{t:.2f}" for t in r["temps_c"]),
                "|".join(r["alarm_codes"]),
            ])

        output.seek(0)
        headers = {"Content-Disposition": f'attachment; filename="cellguard_{sid}.csv"'}
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)

    # --- Web Dashboard Serving at `/` ---
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/", response_class=HTMLResponse)
    def serve_dashboard():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return HTMLResponse(
            "<html><body style='background:#0b111e;color:#e2e8f0;font-family:sans-serif;padding:2rem'>"
            "<h1>CellGuard Telemetry Backend Running</h1>"
            "<p>Dashboard static bundle not built yet. Run <code>npm run build</code> inside <code>dashboard/</code>.</p>"
            "</body></html>",
            status_code=200,
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("CELLGUARD_HOST", "127.0.0.1")
    port = int(os.getenv("CELLGUARD_PORT", "8006"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)
