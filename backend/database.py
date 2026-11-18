"""SQLite Persistence Layer for CellGuard Discharge Sessions, Alarms & Calibration."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class CellGuardDatabase:
    """Thread-safe SQLite storage for CellGuard battery telemetry & configuration."""

    def __init__(self, db_path: str = "./cellguard_telemetry.db") -> None:
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    dataset_id TEXT,
                    series_cells INTEGER NOT NULL,
                    nominal_capacity_mah REAL NOT NULL,
                    r_dc_nominal_cell_mohm REAL NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telemetry_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp_s REAL NOT NULL,
                    pack_voltage_v REAL NOT NULL,
                    current_a REAL NOT NULL,
                    power_w REAL NOT NULL,
                    cell_voltages_json TEXT NOT NULL,
                    cell_min_v REAL NOT NULL,
                    cell_max_v REAL NOT NULL,
                    cell_delta_mv REAL NOT NULL,
                    temps_json TEXT NOT NULL,
                    dtdt_json TEXT NOT NULL,
                    temp_max_c REAL NOT NULL,
                    dtdt_max_c_per_min REAL NOT NULL,
                    soc_percent REAL NOT NULL,
                    soc_ocv_est_percent REAL NOT NULL,
                    soh_percent REAL NOT NULL,
                    soh_capacity_percent REAL NOT NULL,
                    soh_resistance_percent REAL NOT NULL,
                    mah_discharged REAL NOT NULL,
                    wh_discharged REAL NOT NULL,
                    r_dc_pack_ohm REAL NOT NULL,
                    r_dc_cell_mohm REAL NOT NULL,
                    ocv_est_cell_v REAL NOT NULL,
                    rest_seconds REAL NOT NULL,
                    rdc_step_count INTEGER NOT NULL,
                    alarms_json TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS idx_samples_session_ts
                    ON telemetry_samples (session_id, timestamp_s);

                CREATE TABLE IF NOT EXISTS alarm_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp_s REAL NOT NULL,
                    code TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS kv_config (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_session(
        self,
        session_id: str,
        title: str,
        series_cells: int,
        nominal_capacity_mah: float,
        r_dc_nominal_cell_mohm: float,
        dataset_id: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions
                (session_id, title, dataset_id, series_cells, nominal_capacity_mah, r_dc_nominal_cell_mohm, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    title,
                    dataset_id,
                    series_cells,
                    nominal_capacity_mah,
                    r_dc_nominal_cell_mohm,
                    self._now_iso(),
                ),
            )

    def clear_session_samples(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM telemetry_samples WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM alarm_events WHERE session_id = ?", (session_id,))

    def insert_frames_batch(self, session_id: str, frames: List[Dict[str, Any]]) -> None:
        now = self._now_iso()
        sample_rows = []
        alarm_rows = []
        seen_alarm_state = set()

        for f in frames:
            sample_rows.append(
                (
                    session_id,
                    f["timestamp_s"],
                    f["pack_voltage_v"],
                    f["current_a"],
                    f["power_w"],
                    json.dumps(f["cell_voltages_v"]),
                    f["cell_min_v"],
                    f["cell_max_v"],
                    f["cell_delta_mv"],
                    json.dumps(f["temps_c"]),
                    json.dumps(f["dtdt_c_per_min"]),
                    f["temp_max_c"],
                    f["dtdt_max_c_per_min"],
                    f["soc_percent"],
                    f["soc_ocv_est_percent"],
                    f["soh_percent"],
                    f["soh_capacity_percent"],
                    f["soh_resistance_percent"],
                    f["mah_discharged"],
                    f["wh_discharged"],
                    f["r_dc_pack_ohm"],
                    f["r_dc_cell_mohm"],
                    f["ocv_est_cell_v"],
                    f["rest_seconds"],
                    f["rdc_step_count"],
                    json.dumps(f["alarms"]),
                )
            )
            current_codes = {a["code"] for a in f["alarms"]}
            for a in f["alarms"]:
                if a["code"] not in seen_alarm_state:
                    alarm_rows.append(
                        (session_id, f["timestamp_s"], a["code"], a["severity"], a["message"], 0, now)
                    )
            seen_alarm_state = current_codes

        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO telemetry_samples (
                    session_id, timestamp_s, pack_voltage_v, current_a, power_w,
                    cell_voltages_json, cell_min_v, cell_max_v, cell_delta_mv,
                    temps_json, dtdt_json, temp_max_c, dtdt_max_c_per_min,
                    soc_percent, soc_ocv_est_percent, soh_percent,
                    soh_capacity_percent, soh_resistance_percent,
                    mah_discharged, wh_discharged, r_dc_pack_ohm, r_dc_cell_mohm,
                    ocv_est_cell_v, rest_seconds, rdc_step_count, alarms_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                sample_rows,
            )
            if alarm_rows:
                conn.executemany(
                    """
                    INSERT INTO alarm_events
                    (session_id, timestamp_s, code, severity, message, acknowledged, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    alarm_rows,
                )

    def insert_single_frame(self, session_id: str, frame: Dict[str, Any]) -> None:
        self.insert_frames_batch(session_id, [frame])

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.*, COUNT(t.id) AS sample_count
                FROM sessions s
                LEFT JOIN telemetry_samples t ON t.session_id = s.session_id
                GROUP BY s.session_id
                ORDER BY s.created_at DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def get_history(self, session_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM telemetry_samples
                WHERE session_id = ?
                ORDER BY timestamp_s ASC, id ASC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
            return [self._decode_sample_row(r) for r in rows]

    def get_latest_sample(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM telemetry_samples
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            return self._decode_sample_row(row) if row else None

    def get_alarms(self, session_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    """
                    SELECT * FROM alarm_events
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM alarm_events ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def acknowledge_alarms(self, session_id: Optional[str] = None) -> int:
        with self._connect() as conn:
            if session_id:
                cur = conn.execute(
                    "UPDATE alarm_events SET acknowledged = 1 WHERE session_id = ? AND acknowledged = 0",
                    (session_id,),
                )
            else:
                cur = conn.execute("UPDATE alarm_events SET acknowledged = 1 WHERE acknowledged = 0")
            return cur.rowcount

    def save_kv(self, key: str, value: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO kv_config (key, value_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, json.dumps(value), self._now_iso()),
            )

    def load_kv(self, key: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT value_json FROM kv_config WHERE key = ?", (key,)).fetchone()
            return json.loads(row["value_json"]) if row else None

    @staticmethod
    def _decode_sample_row(row: sqlite3.Row) -> Dict[str, Any]:
        cells = json.loads(row["cell_voltages_json"])
        alarms = json.loads(row["alarms_json"])
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "timestamp_s": row["timestamp_s"],
            "series_cells": len(cells),
            "pack_voltage_v": row["pack_voltage_v"],
            "current_a": row["current_a"],
            "power_w": row["power_w"],
            "cell_voltages_v": cells,
            "cell_min_v": row["cell_min_v"],
            "cell_max_v": row["cell_max_v"],
            "cell_delta_mv": row["cell_delta_mv"],
            "temps_c": json.loads(row["temps_json"]),
            "dtdt_c_per_min": json.loads(row["dtdt_json"]),
            "temp_max_c": row["temp_max_c"],
            "dtdt_max_c_per_min": row["dtdt_max_c_per_min"],
            "soc_percent": row["soc_percent"],
            "soc_ocv_est_percent": row["soc_ocv_est_percent"],
            "soh_percent": row["soh_percent"],
            "soh_capacity_percent": row["soh_capacity_percent"],
            "soh_resistance_percent": row["soh_resistance_percent"],
            "mah_discharged": row["mah_discharged"],
            "wh_discharged": row["wh_discharged"],
            "r_dc_pack_ohm": row["r_dc_pack_ohm"],
            "r_dc_cell_mohm": row["r_dc_cell_mohm"],
            "ocv_est_cell_v": row["ocv_est_cell_v"],
            "rest_seconds": row["rest_seconds"],
            "rdc_step_count": row["rdc_step_count"],
            "alarms": alarms,
            "alarm_codes": [a["code"] for a in alarms],
        }
