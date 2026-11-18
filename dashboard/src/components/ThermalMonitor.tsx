import React from "react";
import type { AlarmThresholds, TelemetrySample } from "../types";

interface ThermalMonitorProps {
  sample: TelemetrySample;
  thresholds: AlarmThresholds;
}

const PROBE_LABELS = [
  "NTC1 · Cell Core A",
  "NTC2 · Cell Core B",
  "NTC3 · BMS / Busbar",
  "NTC4 · Shunt / Ambient",
];

export const ThermalMonitor: React.FC<ThermalMonitorProps> = ({ sample, thresholds }) => {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 className="card-title">NTC Steinhart-Hart Thermal Array &amp; dT/dt Runaway Derivative</h3>
          <span className="card-meta">
            Max Temp: {sample.temp_max_c.toFixed(2)} °C · Peak Slope: {sample.dtdt_max_c_per_min.toFixed(2)} °C/min
          </span>
        </div>
        <span
          className={`pill ${
            sample.temp_max_c >= thresholds.temp_crit_c || sample.dtdt_max_c_per_min >= thresholds.dtdt_crit_c_per_min
              ? "pill-crit"
              : sample.temp_max_c >= thresholds.temp_warn_c || sample.dtdt_max_c_per_min >= thresholds.dtdt_warn_c_per_min
              ? "pill-warn"
              : "pill-ok"
          }`}
        >
          {sample.dtdt_max_c_per_min >= thresholds.dtdt_crit_c_per_min
            ? "RUNAWAY ALERT"
            : sample.temp_max_c >= thresholds.temp_warn_c
            ? "THERMAL WARN"
            : "NOMINAL"}
        </span>
      </div>

      <div className="ntc-grid">
        {sample.temps_c.map((temp, idx) => {
          const slope = sample.dtdt_c_per_min[idx] ?? 0;
          const isCrit = temp >= thresholds.temp_crit_c || slope >= thresholds.dtdt_crit_c_per_min;
          const isWarn = !isCrit && (temp >= thresholds.temp_warn_c || slope >= thresholds.dtdt_warn_c_per_min);

          return (
            <div key={idx} className={`ntc-tile ${isCrit ? "crit" : isWarn ? "warn" : ""}`}>
              <div className="kpi-label">{PROBE_LABELS[idx] ?? `NTC${idx + 1}`}</div>
              <div
                className="kpi-value"
                style={{
                  fontSize: "1.35rem",
                  color: isCrit ? "#f87171" : isWarn ? "#fbbf24" : "#34d399",
                }}
              >
                {temp.toFixed(2)} °C
              </div>
              <div className="kpi-sub" style={{ fontFamily: "monospace" }}>
                dT/dt: {slope >= 0 ? "+" : ""}
                {slope.toFixed(2)} °C/min
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
