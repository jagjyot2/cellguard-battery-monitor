import React from "react";
import type { TelemetrySample } from "../types";

interface CellBalanceChartProps {
  sample: TelemetrySample;
}

export const CellBalanceChart: React.FC<CellBalanceChartProps> = ({ sample }) => {
  const cells = sample.cell_voltages_v;
  const minDomain = 2.5;
  const maxDomain = 4.35;

  const deltaColor =
    sample.cell_delta_mv >= 150
      ? "pill-crit"
      : sample.cell_delta_mv >= 50
      ? "pill-warn"
      : "pill-ok";

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Per-Cell Group Voltage Distribution ({sample.series_cells}S)</h3>
          <span className="card-meta">
            Min: {sample.cell_min_v.toFixed(4)}V · Max: {sample.cell_max_v.toFixed(4)}V
          </span>
        </div>
        <span className={`pill ${deltaColor}`}>Δ {sample.cell_delta_mv.toFixed(1)} mV</span>
      </div>

      <svg
        width="100%"
        height="220"
        viewBox="0 0 540 220"
        role="img"
        aria-label="Per-cell group voltage bar chart"
      >
        {[2.7, 3.0, 3.4, 3.8, 4.2].map((v) => {
          const y = 185 - ((v - minDomain) / (maxDomain - minDomain)) * 160;
          return (
            <g key={v}>
              <line x1="48" y1={y} x2="520" y2={y} stroke="#1e293b" strokeDasharray="3 3" />
              <text x="42" y={y + 3} textAnchor="end" fill="#64748b" fontSize="10" fontFamily="monospace">
                {v.toFixed(1)}V
              </text>
            </g>
          );
        })}

        {cells.map((v, idx) => {
          const slotW = 460 / Math.max(1, cells.length);
          const barW = Math.min(52, slotW * 0.62);
          const x = 56 + idx * slotW + (slotW - barW) / 2;
          const clamped = Math.max(minDomain, Math.min(maxDomain, v));
          const barH = ((clamped - minDomain) / (maxDomain - minDomain)) * 160;
          const y = 185 - barH;

          const isMin = Math.abs(v - sample.cell_min_v) < 1e-4 && sample.cell_delta_mv >= 30;
          const fill =
            v >= 4.21 || v <= 2.85
              ? "#ef4444"
              : isMin
              ? "#f59e0b"
              : "#10b981";

          return (
            <g key={idx}>
              <rect x={x} y={25} width={barW} height={160} rx="5" fill="#0b1220" stroke="#1e293b" />
              <rect x={x} y={y} width={barW} height={barH} rx="5" fill={fill} fillOpacity="0.88" />
              <text
                x={x + barW / 2}
                y={y - 6}
                textAnchor="middle"
                fill="#e2e8f0"
                fontSize="10.5"
                fontFamily="monospace"
                fontWeight="700"
              >
                {v.toFixed(3)}V
              </text>
              <text
                x={x + barW / 2}
                y={204}
                textAnchor="middle"
                fill="#94a3b8"
                fontSize="11"
                fontWeight="600"
              >
                Cell {idx + 1}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};
