import React from "react";
import type { TelemetrySample } from "../types";

interface PackGaugesProps {
  sample: TelemetrySample;
}

interface RadialGaugeProps {
  label: string;
  value: number;
  unit: string;
  color: string;
  sub: string;
}

const RadialGauge: React.FC<RadialGaugeProps> = ({ label, value, unit, color, sub }) => {
  const clamped = Math.max(0, Math.min(100, value));
  const radius = 38;
  const circ = 2 * Math.PI * radius;
  const dashOffset = circ * (1 - clamped / 100);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.25rem" }}>
      <svg width="96" height="96" viewBox="0 0 96 96" aria-label={label}>
        <circle cx="48" cy="48" r={radius} fill="none" stroke="#1e293b" strokeWidth="8" />
        <circle
          cx="48"
          cy="48"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={dashOffset}
          transform="rotate(-90 48 48)"
        />
        <text x="48" y="47" textAnchor="middle" fill="#e6edf7" fontSize="15" fontWeight="700" fontFamily="monospace">
          {clamped.toFixed(1)}
          {unit}
        </text>
        <text x="48" y="62" textAnchor="middle" fill="#94a3b8" fontSize="9.5" fontWeight="600">
          {label}
        </text>
      </svg>
      <span className="kpi-sub">{sub}</span>
    </div>
  );
};

export const PackGauges: React.FC<PackGaugesProps> = ({ sample }) => {
  const socColor = sample.soc_percent > 30 ? "#10b981" : sample.soc_percent > 15 ? "#f59e0b" : "#ef4444";
  const sohColor = sample.soh_percent >= 90 ? "#22d3ee" : sample.soh_percent >= 80 ? "#f59e0b" : "#ef4444";

  return (
    <div className="grid-kpi">
      <div className="kpi-card">
        <span className="kpi-label">Pack Bus Voltage ({sample.series_cells}S)</span>
        <span className="kpi-value" style={{ color: "#22d3ee" }}>
          {sample.pack_voltage_v.toFixed(3)} V
        </span>
        <span className="kpi-sub">
          OCV Est/Cell: {sample.ocv_est_cell_v.toFixed(3)} V
        </span>
      </div>

      <div className="kpi-card">
        <span className="kpi-label">Pack Current &amp; Power</span>
        <span className="kpi-value" style={{ color: sample.current_a >= 0 ? "#fbbf24" : "#34d399" }}>
          {sample.current_a.toFixed(2)} A
        </span>
        <span className="kpi-sub">
          {sample.power_w.toFixed(1)} W ({sample.current_a >= 0 ? "Discharging" : "Charging"})
        </span>
      </div>

      <div className="kpi-card">
        <span className="kpi-label">Coulomb &amp; Energy Counter</span>
        <span className="kpi-value" style={{ color: "#a78bfa" }}>
          {sample.mah_discharged.toFixed(0)} mAh
        </span>
        <span className="kpi-sub">{sample.wh_discharged.toFixed(2)} Wh delivered</span>
      </div>

      <div className="kpi-card">
        <span className="kpi-label">Dynamic DC-IR (R_dc = dV/dI)</span>
        <span className="kpi-value" style={{ color: sample.r_dc_cell_mohm > 35 ? "#f59e0b" : "#34d399" }}>
          {sample.r_dc_cell_mohm.toFixed(1)} mΩ
        </span>
        <span className="kpi-sub">
          Pack: {(sample.r_dc_pack_ohm * 1000).toFixed(1)} mΩ ({sample.rdc_step_count} steps)
        </span>
      </div>

      <div className="kpi-card" style={{ gridColumn: "span 1" }}>
        <div className="gauge-row">
          <RadialGauge
            label="SoC"
            value={sample.soc_percent}
            unit="%"
            color={socColor}
            sub={`OCV ${sample.soc_ocv_est_percent.toFixed(1)}%`}
          />
          <RadialGauge
            label="SoH"
            value={sample.soh_percent}
            unit="%"
            color={sohColor}
            sub={`Cap ${sample.soh_capacity_percent.toFixed(0)}%`}
          />
        </div>
      </div>
    </div>
  );
};
