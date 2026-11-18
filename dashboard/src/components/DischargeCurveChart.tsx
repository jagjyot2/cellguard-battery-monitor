import React from "react";
import type { TelemetrySample } from "../types";

interface DischargeCurveChartProps {
  samples: TelemetrySample[];
  cursorIdx: number;
  onSelectIndex: (idx: number) => void;
}

export const DischargeCurveChart: React.FC<DischargeCurveChartProps> = ({
  samples,
  cursorIdx,
  onSelectIndex,
}) => {
  if (samples.length === 0) {
    return (
      <div className="card">
        <p className="kpi-sub">No telemetry history points loaded.</p>
      </div>
    );
  }

  const w = 680;
  const h = 240;
  const padL = 52;
  const padR = 52;
  const padT = 20;
  const padB = 34;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;

  const tMin = samples[0].timestamp_s;
  const tMax = Math.max(tMin + 1, samples[samples.length - 1].timestamp_s);

  const vVals = samples.map((s) => s.pack_voltage_v);
  const vMin = Math.floor((Math.min(...vVals) - 0.5) * 2) / 2;
  const vMax = Math.ceil((Math.max(...vVals) + 0.5) * 2) / 2;

  const iMax = Math.max(10, Math.ceil(Math.max(...samples.map((s) => Math.abs(s.current_a))) / 5) * 5);

  const mapX = (t: number) => padL + ((t - tMin) / (tMax - tMin)) * plotW;
  const mapV = (v: number) => padT + plotH - ((v - vMin) / Math.max(0.5, vMax - vMin)) * plotH;
  const mapSoc = (soc: number) => padT + plotH - (Math.max(0, Math.min(100, soc)) / 100) * plotH;
  const mapI = (curr: number) => padT + plotH - (Math.max(0, Math.min(iMax, curr)) / iMax) * plotH;

  const makePath = (pts: [number, number][]) =>
    pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

  const vPath = makePath(samples.map((s) => [mapX(s.timestamp_s), mapV(s.pack_voltage_v)]));
  const socPath = makePath(samples.map((s) => [mapX(s.timestamp_s), mapSoc(s.soc_percent)]));
  const iPath = makePath(samples.map((s) => [mapX(s.timestamp_s), mapI(s.current_a)]));

  const cur = samples[Math.min(cursorIdx, samples.length - 1)];
  const curX = mapX(cur.timestamp_s);

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 className="card-title">21700 Discharge Curve, Load Current &amp; Fused SoC Trend</h3>
          <span className="card-meta">
            t={cur.timestamp_s.toFixed(0)}s · V_pack={cur.pack_voltage_v.toFixed(2)}V · I={cur.current_a.toFixed(1)}A · SoC={cur.soc_percent.toFixed(1)}% · SoH={cur.soh_percent.toFixed(1)}%
          </span>
        </div>
        <div style={{ display: "flex", gap: "0.75rem", fontSize: "0.74rem" }}>
          <span style={{ color: "#22d3ee" }}>● Pack V</span>
          <span style={{ color: "#10b981" }}>● SoC %</span>
          <span style={{ color: "#f59e0b" }}>● Current A</span>
        </div>
      </div>

      <svg width="100%" height="240" viewBox={`0 0 ${w} ${h}`}>
        {[0, 25, 50, 75, 100].map((pct) => {
          const y = mapSoc(pct);
          const vLabel = vMin + (pct / 100) * (vMax - vMin);
          return (
            <g key={pct}>
              <line x1={padL} y1={y} x2={w - padR} y2={y} stroke="#1e293b" strokeDasharray="3 3" />
              <text x={padL - 6} y={y + 3} textAnchor="end" fill="#22d3ee" fontSize="10" fontFamily="monospace">
                {vLabel.toFixed(1)}V
              </text>
              <text x={w - padR + 6} y={y + 3} textAnchor="start" fill="#10b981" fontSize="10" fontFamily="monospace">
                {pct}%
              </text>
            </g>
          );
        })}

        <path d={iPath} fill="none" stroke="#f59e0b" strokeWidth="1.5" strokeOpacity="0.65" />
        <path d={socPath} fill="none" stroke="#10b981" strokeWidth="2.1" />
        <path d={vPath} fill="none" stroke="#22d3ee" strokeWidth="2.3" />

        <line x1={curX} y1={padT} x2={curX} y2={padT + plotH} stroke="#e2e8f0" strokeDasharray="4 3" strokeOpacity="0.6" />
        <circle cx={curX} cy={mapV(cur.pack_voltage_v)} r="4" fill="#22d3ee" />
        <circle cx={curX} cy={mapSoc(cur.soc_percent)} r="4" fill="#10b981" />

        <text x={padL} y={h - 8} fill="#64748b" fontSize="10" fontFamily="monospace">
          {tMin.toFixed(0)}s
        </text>
        <text x={w - padR} y={h - 8} textAnchor="end" fill="#64748b" fontSize="10" fontFamily="monospace">
          {tMax.toFixed(0)}s
        </text>
      </svg>

      <div className="scrub-row">
        <span className="card-meta">Timeline Scrub:</span>
        <input
          type="range"
          min={0}
          max={Math.max(0, samples.length - 1)}
          value={Math.min(cursorIdx, Math.max(0, samples.length - 1))}
          onChange={(e) => onSelectIndex(Number(e.target.value))}
        />
        <span className="card-meta">
          Frame {Math.min(cursorIdx + 1, samples.length)}/{samples.length}
        </span>
      </div>
    </div>
  );
};
