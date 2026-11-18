import React, { useEffect, useState } from "react";
import type { AlarmLogRow, AlarmThresholds, TelemetrySample } from "../types";

interface AlarmConsoleProps {
  sample: TelemetrySample;
  alarmLogs: AlarmLogRow[];
  thresholds: AlarmThresholds;
  onAckAlarms: () => Promise<void>;
  onSaveThresholds: (next: AlarmThresholds) => Promise<void>;
}

export const AlarmConsole: React.FC<AlarmConsoleProps> = ({
  sample,
  alarmLogs,
  thresholds,
  onAckAlarms,
  onSaveThresholds,
}) => {
  const [draft, setDraft] = useState<AlarmThresholds>(thresholds);
  const [saving, setSaving] = useState(false);
  const [savedBanner, setSavedBanner] = useState("");

  useEffect(() => {
    setDraft(thresholds);
  }, [thresholds]);

  const handleField = (key: keyof AlarmThresholds, value: string) => {
    const parsed = Number(value);
    if (!Number.isNaN(parsed)) {
      setDraft((prev) => ({ ...prev, [key]: parsed }));
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSavedBanner("");
    try {
      await onSaveThresholds(draft);
      setSavedBanner("Alarm rules updated in backend engine.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid-two">
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Alarm Console &amp; Audit History</h3>
            <span className="card-meta">
              Active Frame Alarms: {sample.alarms.length} · Logged Events: {alarmLogs.length}
            </span>
          </div>
          <button type="button" onClick={() => void onAckAlarms()}>
            Acknowledge All
          </button>
        </div>

        {sample.alarms.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.45rem", marginBottom: "0.75rem" }}>
            {sample.alarms.map((a, idx) => (
              <span key={idx} className={`pill ${a.severity === "CRIT" ? "pill-crit" : "pill-warn"}`}>
                {a.code}: {a.message}
              </span>
            ))}
          </div>
        )}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time (s)</th>
                <th>Severity</th>
                <th>Code</th>
                <th>Message</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {alarmLogs.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ color: "#64748b", textAlign: "center" }}>
                    No alarm events recorded for this session.
                  </td>
                </tr>
              ) : (
                alarmLogs.map((row) => (
                  <tr key={row.id}>
                    <td style={{ fontFamily: "monospace" }}>{row.timestamp_s.toFixed(1)}</td>
                    <td>
                      <span className={`pill ${row.severity === "CRIT" ? "pill-crit" : "pill-warn"}`}>
                        {row.severity}
                      </span>
                    </td>
                    <td style={{ fontFamily: "monospace" }}>{row.code}</td>
                    <td>{row.message}</td>
                    <td>{row.acknowledged ? "ACK" : "ACTIVE"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Configurable Alarm Thresholds</h3>
            <span className="card-meta">Telemetry alert rules only (no pack disconnect FETs)</span>
          </div>
        </div>

        <form onSubmit={(e) => void handleSave(e)}>
          <div className="form-grid">
            <label className="form-field">
              Cell OV Warn (V)
              <input
                type="number"
                step="0.01"
                value={draft.cell_ov_warn_v}
                onChange={(e) => handleField("cell_ov_warn_v", e.target.value)}
              />
            </label>
            <label className="form-field">
              Cell UV Warn (V)
              <input
                type="number"
                step="0.01"
                value={draft.cell_uv_warn_v}
                onChange={(e) => handleField("cell_uv_warn_v", e.target.value)}
              />
            </label>
            <label className="form-field">
              Cell Delta Warn (mV)
              <input
                type="number"
                step="1"
                value={draft.cell_delta_warn_mv}
                onChange={(e) => handleField("cell_delta_warn_mv", e.target.value)}
              />
            </label>
            <label className="form-field">
              Max Discharge (A)
              <input
                type="number"
                step="0.5"
                value={draft.max_discharge_a}
                onChange={(e) => handleField("max_discharge_a", e.target.value)}
              />
            </label>
            <label className="form-field">
              Temp Warn (°C)
              <input
                type="number"
                step="0.5"
                value={draft.temp_warn_c}
                onChange={(e) => handleField("temp_warn_c", e.target.value)}
              />
            </label>
            <label className="form-field">
              Temp Crit (°C)
              <input
                type="number"
                step="0.5"
                value={draft.temp_crit_c}
                onChange={(e) => handleField("temp_crit_c", e.target.value)}
              />
            </label>
            <label className="form-field">
              dT/dt Warn (°C/min)
              <input
                type="number"
                step="0.2"
                value={draft.dtdt_warn_c_per_min}
                onChange={(e) => handleField("dtdt_warn_c_per_min", e.target.value)}
              />
            </label>
            <label className="form-field">
              dT/dt Runaway Crit (°C/min)
              <input
                type="number"
                step="0.2"
                value={draft.dtdt_crit_c_per_min}
                onChange={(e) => handleField("dtdt_crit_c_per_min", e.target.value)}
              />
            </label>
          </div>
          <div style={{ marginTop: "0.9rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? "Saving..." : "Apply Thresholds"}
            </button>
            {savedBanner && <span style={{ color: "#34d399", fontSize: "0.8rem" }}>{savedBanner}</span>}
          </div>
        </form>
      </div>
    </div>
  );
};
