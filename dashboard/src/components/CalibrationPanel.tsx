import React, { useState } from "react";
import { api } from "../api";
import type { CalibrationCalcRequest, CalibrationCalcResponse } from "../types";

export const CalibrationPanel: React.FC = () => {
  const [form, setForm] = useState<CalibrationCalcRequest>({
    r_shunt_mohm: 1.0,
    max_expected_current_a: 60.0,
    series_cells: 4,
    nominal_capacity_mah: 5000.0,
    current_meas1: 0.02,
    current_ref1: 0.0,
    current_meas2: 19.85,
    current_ref2: 20.0,
    vbus_meas1: 12.04,
    vbus_ref1: 12.0,
    vbus_meas2: 16.86,
    vbus_ref2: 16.8,
    tap_channel: 1,
    tap_meas1: 3.01,
    tap_ref1: 3.0,
    tap_meas2: 4.215,
    tap_ref2: 4.2,
  });

  const [result, setResult] = useState<CalibrationCalcResponse | null>(null);
  const [error, setError] = useState("");

  const setNum = (k: keyof CalibrationCalcRequest, v: string) => {
    const num = Number(v);
    if (!Number.isNaN(num)) {
      setForm((prev) => ({ ...prev, [k]: num }));
    }
  };

  const handleCalculate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await api.calculateCalibration(form);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calibration computation failed");
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Interactive INA226 Shunt &amp; 2-Point Divider Calibration Calculator</h3>
          <span className="card-meta">
            Computes TI INA226 CAL register, LSBs, two-point gain/offset, and ESP32 NVS CLI commands
          </span>
        </div>
      </div>

      <form onSubmit={(e) => void handleCalculate(e)}>
        <div className="form-grid">
          <label className="form-field">
            Shunt R (mΩ)
            <input
              type="number"
              step="0.05"
              value={form.r_shunt_mohm}
              onChange={(e) => setNum("r_shunt_mohm", e.target.value)}
            />
          </label>
          <label className="form-field">
            Max Current (A)
            <input
              type="number"
              step="1"
              value={form.max_expected_current_a}
              onChange={(e) => setNum("max_expected_current_a", e.target.value)}
            />
          </label>
          <label className="form-field">
            Series Cells (1-6S)
            <input
              type="number"
              min={1}
              max={6}
              value={form.series_cells}
              onChange={(e) => setNum("series_cells", e.target.value)}
            />
          </label>
          <label className="form-field">
            Pack Cap (mAh)
            <input
              type="number"
              step="100"
              value={form.nominal_capacity_mah}
              onChange={(e) => setNum("nominal_capacity_mah", e.target.value)}
            />
          </label>
          <label className="form-field">
            Curr Pt1 Meas / Ref (A)
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <input
                type="number"
                step="0.001"
                value={form.current_meas1}
                onChange={(e) => setNum("current_meas1", e.target.value)}
                style={{ width: "50%" }}
              />
              <input
                type="number"
                step="0.001"
                value={form.current_ref1}
                onChange={(e) => setNum("current_ref1", e.target.value)}
                style={{ width: "50%" }}
              />
            </div>
          </label>
          <label className="form-field">
            Curr Pt2 Meas / Ref (A)
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <input
                type="number"
                step="0.001"
                value={form.current_meas2}
                onChange={(e) => setNum("current_meas2", e.target.value)}
                style={{ width: "50%" }}
              />
              <input
                type="number"
                step="0.001"
                value={form.current_ref2}
                onChange={(e) => setNum("current_ref2", e.target.value)}
                style={{ width: "50%" }}
              />
            </div>
          </label>
          <label className="form-field">
            Tap Channel (1-6)
            <input
              type="number"
              min={1}
              max={6}
              value={form.tap_channel}
              onChange={(e) => setNum("tap_channel", e.target.value)}
            />
          </label>
          <label className="form-field">
            Tap Pt1 Meas / Ref (V)
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <input
                type="number"
                step="0.001"
                value={form.tap_meas1}
                onChange={(e) => setNum("tap_meas1", e.target.value)}
                style={{ width: "50%" }}
              />
              <input
                type="number"
                step="0.001"
                value={form.tap_ref1}
                onChange={(e) => setNum("tap_ref1", e.target.value)}
                style={{ width: "50%" }}
              />
            </div>
          </label>
          <label className="form-field">
            Tap Pt2 Meas / Ref (V)
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <input
                type="number"
                step="0.001"
                value={form.tap_meas2}
                onChange={(e) => setNum("tap_meas2", e.target.value)}
                style={{ width: "50%" }}
              />
              <input
                type="number"
                step="0.001"
                value={form.tap_ref2}
                onChange={(e) => setNum("tap_ref2", e.target.value)}
                style={{ width: "50%" }}
              />
            </div>
          </label>
        </div>

        <div style={{ marginTop: "0.9rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <button type="submit" className="btn-primary">
            Compute Register &amp; NVS Coefficients
          </button>
          {error && <span style={{ color: "#f87171", fontSize: "0.82rem" }}>{error}</span>}
        </div>
      </form>

      {result && (
        <div style={{ marginTop: "1rem" }}>
          <div className="grid-kpi">
            <div className="kpi-card">
              <span className="kpi-label">INA226 CAL Register</span>
              <span className="kpi-value" style={{ fontSize: "1.2rem", color: "#22d3ee" }}>
                {result.ina226.cal_register} ({result.ina226.cal_register_hex})
              </span>
              <span className="kpi-sub">
                Full-scale Shunt: {result.ina226.full_scale_shunt_mv.toFixed(2)} mV ({" "}
                {result.ina226.within_81_92mv_limit ? "OK ≤ 81.92mV" : "EXCEEDS 81.92mV"} )
              </span>
            </div>
            <div className="kpi-card">
              <span className="kpi-label">Effective Current / Power LSB</span>
              <span className="kpi-value" style={{ fontSize: "1.2rem", color: "#34d399" }}>
                {(result.ina226.effective_current_lsb_a * 1000).toFixed(4)} mA/bit
              </span>
              <span className="kpi-sub">Power LSB: {(result.ina226.power_lsb_w * 1000).toFixed(3)} mW/bit</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-label">Current 2-Pt Fit</span>
              <span className="kpi-value" style={{ fontSize: "1.2rem", color: "#a78bfa" }}>
                g={result.current_calibration.gain.toFixed(5)}
              </span>
              <span className="kpi-sub">offset={result.current_calibration.offset_a.toFixed(5)} A</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-label">Tap CH{result.tap_calibration.channel} 2-Pt Fit</span>
              <span className="kpi-value" style={{ fontSize: "1.2rem", color: "#fbbf24" }}>
                g={result.tap_calibration.gain.toFixed(5)}
              </span>
              <span className="kpi-sub">
                Ratio {result.tap_calibration.divider_ratio}:1 · off={result.tap_calibration.offset_v.toFixed(5)} V
              </span>
            </div>
          </div>
          <div className="cli-box">{result.esp32_cli_commands.join("\n")}</div>
        </div>
      )}
    </div>
  );
};
