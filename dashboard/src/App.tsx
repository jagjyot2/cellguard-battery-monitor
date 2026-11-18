import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { AlarmConsole } from "./components/AlarmConsole";
import { CalibrationPanel } from "./components/CalibrationPanel";
import { CellBalanceChart } from "./components/CellBalanceChart";
import { DischargeCurveChart } from "./components/DischargeCurveChart";
import { PackGauges } from "./components/PackGauges";
import { ThermalMonitor } from "./components/ThermalMonitor";
import type {
  AlarmLogRow,
  AlarmThresholds,
  DatasetMeta,
  HealthResponse,
  TelemetrySample,
} from "./types";

type TabId = "overview" | "alarms" | "calibration";

export function App() {
  const [tab, setTab] = useState<TabId>("overview");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [datasets, setDatasets] = useState<DatasetMeta[]>([]);
  const [activeSession, setActiveSession] = useState<string>("4s_50e_nominal");
  const [samples, setSamples] = useState<TelemetrySample[]>([]);
  const [cursorIdx, setCursorIdx] = useState<number>(0);
  const [alarmLogs, setAlarmLogs] = useState<AlarmLogRow[]>([]);
  const [thresholds, setThresholds] = useState<AlarmThresholds | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");

  const loadSessionData = useCallback(async (sessionId?: string) => {
    try {
      setError("");
      const [h, sess, hist, alms, thr] = await Promise.all([
        api.getHealth(),
        api.getSessions(),
        api.getHistory(sessionId),
        api.getAlarms(sessionId),
        api.getThresholds(),
      ]);
      setHealth(h);
      setDatasets(sess.datasets);
      setActiveSession(hist.session_id);
      setSamples(hist.samples);
      setCursorIdx(Math.max(0, hist.samples.length - 1));
      setAlarmLogs(alms.alarms);
      setThresholds(thr);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load CellGuard telemetry");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSessionData();
  }, [loadSessionData]);

  const handleReplay = async (datasetId: string) => {
    setLoading(true);
    try {
      await api.replayDataset(datasetId);
      await loadSessionData(datasetId);
    } finally {
      setLoading(false);
    }
  };

  const handleAckAlarms = async () => {
    await api.ackAlarms(activeSession);
    const alms = await api.getAlarms(activeSession);
    setAlarmLogs(alms.alarms);
  };

  const handleSaveThresholds = async (next: AlarmThresholds) => {
    const res = await api.updateThresholds(next);
    setThresholds(res.thresholds);
  };

  const currentSample = samples[Math.min(cursorIdx, Math.max(0, samples.length - 1))];

  return (
    <div className="app-shell">
      <div className="safety-banner">
        <div style={{ display: "flex", alignItems: "center", gap: "0.65rem", flexWrap: "wrap" }}>
          <span className="safety-badge">NON-INVASIVE TELEMETRY ONLY</span>
          <span>
            Must operate alongside an <strong>external commercial BMS</strong> and{" "}
            <strong>inline main fuse</strong>. Zero balancing, charging, or FET switching.
          </span>
        </div>
        {health && (
          <span className="card-meta">
            v{health.version} · monitor_only={String(health.safety.monitor_only)}
          </span>
        )}
      </div>

      <header className="topbar">
        <div>
          <h1 className="brand-title">
            <span style={{ color: "#22d3ee" }}>CellGuard</span> 21700 Pack Monitor &amp; Health Analytics
          </h1>
          <p className="brand-sub">
            INA226 16-bit Kelvin Shunt · Steinhart-Hart NTC dT/dt · OCV+Coulomb SoC · Dynamic R_dc &amp; SoH
          </p>
        </div>

        <div className="controls-row">
          <select
            aria-label="Bench Replay Dataset"
            value={activeSession}
            onChange={(e) => void handleReplay(e.target.value)}
          >
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title}
              </option>
            ))}
          </select>

          <button type="button" onClick={() => void handleReplay(activeSession)}>
            Replay Dataset
          </button>

          <a className="btn-link btn-primary" href={api.getCsvExportUrl(activeSession)} download>
            Export CSV
          </a>
        </div>
      </header>

      <nav className="tabs-bar">
        <button
          type="button"
          className={`tab-btn ${tab === "overview" ? "active" : ""}`}
          onClick={() => setTab("overview")}
        >
          Live Telemetry &amp; Analytics
        </button>
        <button
          type="button"
          className={`tab-btn ${tab === "alarms" ? "active" : ""}`}
          onClick={() => setTab("alarms")}
        >
          Alarms &amp; Thresholds ({alarmLogs.filter((a) => !a.acknowledged).length})
        </button>
        <button
          type="button"
          className={`tab-btn ${tab === "calibration" ? "active" : ""}`}
          onClick={() => setTab("calibration")}
        >
          INA226 &amp; Divider Calibration
        </button>
      </nav>

      {error && (
        <div className="card" style={{ borderColor: "#ef4444", marginBottom: "1rem", color: "#fca5a5" }}>
          {error}
        </div>
      )}

      {loading && !currentSample ? (
        <div className="card">Loading 21700 pack telemetry...</div>
      ) : currentSample && thresholds ? (
        <>
          {tab === "overview" && (
            <>
              <PackGauges sample={currentSample} />
              <div className="grid-two">
                <DischargeCurveChart
                  samples={samples}
                  cursorIdx={cursorIdx}
                  onSelectIndex={setCursorIdx}
                />
                <CellBalanceChart sample={currentSample} />
              </div>
              <ThermalMonitor sample={currentSample} thresholds={thresholds} />
            </>
          )}

          {tab === "alarms" && (
            <AlarmConsole
              sample={currentSample}
              alarmLogs={alarmLogs}
              thresholds={thresholds}
              onAckAlarms={handleAckAlarms}
              onSaveThresholds={handleSaveThresholds}
            />
          )}

          {tab === "calibration" && <CalibrationPanel />}
        </>
      ) : (
        <div className="card">No telemetry session active.</div>
      )}
    </div>
  );
}

export default App;
