"""CellGuard Battery Health Analytics Engine & Sensor Math Mirror.

Mirrors the ESP32 C++ firmware math (`ina226_driver`, `ntc_array`,
`cell_tap_monitor`, `battery_analytics`, and `cal_tool`) so offline replay,
REST telemetry ingestion, calibration tools, and pytest verification remain
mathematically identical to embedded hardware execution.

CRITICAL SAFETY INVARIANT:
CellGuard is strictly a read-only telemetry and analytics system operated
alongside an external commercial BMS and inline main fuse. It implements ZERO
cell balancing, ZERO charging control, and ZERO FET switching.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

# --- Safety Constants (Read-Only Telemetry Only) ---
MONITOR_ONLY: bool = True
BALANCING_SUPPORTED: bool = False
CHARGING_SUPPORTED: bool = False
FET_SWITCHING_SUPPORTED: bool = False

# --- INA226 Datasheet Constants (TI SBOS547A) ---
INA226_SHUNT_LSB_V: float = 2.5e-6     # 2.5 uV/bit
INA226_BUS_LSB_V: float = 1.25e-3      # 1.25 mV/bit
INA226_CAL_NUMERATOR: float = 0.00512  # Internal scaling constant

# --- NTC Steinhart-Hart Defaults (10k @ 25C, Murata NCP18XH103 / 103AT-2) ---
DEFAULT_SH_A: float = 1.129148e-3
DEFAULT_SH_B: float = 2.34125e-4
DEFAULT_SH_C: float = 8.76741e-8
DEFAULT_NTC_R_SERIES: float = 10000.0
DEFAULT_ADC_VREF: float = 3.300

# --- 21700 NMC/INR Open-Circuit Voltage Lookup Table ---
# Matches `k21700OcvLut` in firmware/src/analytics/battery_analytics.cpp
OCV_LUT_21700: Tuple[Tuple[float, float], ...] = (
    (2.50, 0.0),
    (2.80, 1.5),
    (3.00, 3.5),
    (3.15, 6.0),
    (3.25, 10.0),
    (3.35, 16.0),
    (3.42, 22.0),
    (3.48, 28.0),
    (3.53, 35.0),
    (3.58, 42.0),
    (3.63, 50.0),
    (3.69, 58.0),
    (3.76, 66.0),
    (3.84, 74.0),
    (3.92, 82.0),
    (4.00, 89.0),
    (4.07, 94.0),
    (4.14, 98.0),
    (4.20, 100.0),
)

DEFAULT_DIVIDER_RATIOS: Tuple[float, ...] = (2.00, 4.00, 5.99, 7.80, 9.20, 11.00)


# ==============================================================================
# INA226 Precision Register & Calibration Math
# ==============================================================================

def compute_current_lsb(max_expected_current_a: float) -> float:
    """Compute ideal INA226 Current_LSB = I_max / 2^15."""
    if max_expected_current_a <= 0.0:
        raise ValueError("max_expected_current_a must be positive")
    return max_expected_current_a / 32768.0


def compute_cal_register(r_shunt_ohm: float, current_lsb_a: float) -> int:
    """Compute 15-bit INA226 Calibration register CAL = trunc(0.00512 / (I_LSB * R_shunt))."""
    if r_shunt_ohm <= 0.0 or current_lsb_a <= 0.0:
        raise ValueError("r_shunt_ohm and current_lsb_a must be positive")
    raw_cal = INA226_CAL_NUMERATOR / (current_lsb_a * r_shunt_ohm)
    cal = int(math.floor(raw_cal))
    return max(1, min(32767, cal))


def compute_effective_current_lsb(r_shunt_ohm: float, cal_reg: int) -> float:
    """Recover exact Current_LSB implied by truncated integer CAL register."""
    if r_shunt_ohm <= 0.0 or cal_reg < 1:
        raise ValueError("Invalid shunt resistance or CAL register")
    return INA226_CAL_NUMERATOR / (float(cal_reg) * r_shunt_ohm)


def compute_power_lsb(current_lsb_a: float) -> float:
    """INA226 fixed Power_LSB = 25 * Current_LSB."""
    return 25.0 * current_lsb_a


def compute_ina226_calibration_params(
    r_shunt_ohm: float,
    max_expected_current_a: float,
) -> Dict[str, float | int | str]:
    """Compute full INA226 register & LSB calibration summary."""
    ideal_lsb = compute_current_lsb(max_expected_current_a)
    cal_reg = compute_cal_register(r_shunt_ohm, ideal_lsb)
    eff_lsb = compute_effective_current_lsb(r_shunt_ohm, cal_reg)
    pwr_lsb = compute_power_lsb(eff_lsb)
    max_shunt_v_mv = max_expected_current_a * r_shunt_ohm * 1000.0
    return {
        "r_shunt_ohm": r_shunt_ohm,
        "max_expected_current_a": max_expected_current_a,
        "ideal_current_lsb_a": ideal_lsb,
        "cal_register": cal_reg,
        "cal_register_hex": f"0x{cal_reg:04X}",
        "effective_current_lsb_a": eff_lsb,
        "power_lsb_w": pwr_lsb,
        "full_scale_shunt_mv": max_shunt_v_mv,
        "within_81_92mv_limit": max_shunt_v_mv <= 81.92,
    }


def decode_ina226_registers(
    raw_shunt_int16: int,
    raw_bus_uint16: int,
    raw_curr_int16: int,
    current_lsb_a: float,
    current_gain: float = 1.0,
    current_offset_a: float = 0.0,
    vbus_gain: float = 1.0,
    vbus_offset_v: float = 0.0,
) -> Dict[str, float]:
    """Decode signed/unsigned INA226 registers with optional 2-point software calibration."""
    if not (-32768 <= raw_shunt_int16 <= 32767):
        raise ValueError("raw_shunt_int16 out of int16 range")
    if not (0 <= raw_bus_uint16 <= 65535):
        raise ValueError("raw_bus_uint16 out of uint16 range")
    if not (-32768 <= raw_curr_int16 <= 32767):
        raise ValueError("raw_curr_int16 out of int16 range")

    shunt_mv = float(raw_shunt_int16) * (INA226_SHUNT_LSB_V * 1000.0)
    bus_v = (float(raw_bus_uint16) * INA226_BUS_LSB_V) * vbus_gain + vbus_offset_v
    curr_a = (float(raw_curr_int16) * current_lsb_a) * current_gain + current_offset_a
    power_w = bus_v * curr_a
    return {
        "shunt_voltage_mv": shunt_mv,
        "bus_voltage_v": bus_v,
        "current_a": curr_a,
        "power_w": power_w,
    }


def encode_ina226_alert_limit(
    mode: str,
    limit_value: float,
    r_shunt_ohm: float = 0.001,
    power_lsb_w: float = 0.05,
) -> int:
    """Encode Alert Limit register (0x07) value for SOL/SUL/BOL/BUL/POL modes."""
    mode_u = mode.upper()
    if mode_u in ("SOL", "SUL", "SHUNT_OVER_VOLT", "SHUNT_UNDER_VOLT"):
        v_shunt = limit_value * r_shunt_ohm
        counts = int(round(v_shunt / INA226_SHUNT_LSB_V))
        counts = max(-32768, min(32767, counts))
        return counts & 0xFFFF
    if mode_u in ("BOL", "BUL", "BUS_OVER_VOLT", "BUS_UNDER_VOLT"):
        counts = int(round(limit_value / INA226_BUS_LSB_V))
        return max(0, min(32767, counts))
    if mode_u in ("POL", "POWER_OVER_LIMIT"):
        counts = int(round(limit_value / power_lsb_w))
        return max(0, min(65535, counts))
    raise ValueError(f"Unsupported alert mode: {mode}")


# ==============================================================================
# Two-Point Linear Calibration
# ==============================================================================

def compute_two_point_calibration(
    meas1: float,
    ref1: float,
    meas2: float,
    ref2: float,
) -> Tuple[float, float]:
    """Compute (gain, offset) mapping y_cal = gain * x_raw + offset."""
    denom = meas2 - meas1
    if abs(denom) < 1e-6:
        raise ValueError("Degenerate two-point span: meas2 and meas1 are too close")
    gain = (ref2 - ref1) / denom
    offset = ref1 - gain * meas1
    return gain, offset


def apply_linear_calibration(raw_val: float, gain: float, offset: float) -> float:
    return gain * raw_val + offset


# ==============================================================================
# NTC Steinhart-Hart & Thermal Runaway Derivative (dT/dt)
# ==============================================================================

def ntc_voltage_to_resistance(
    v_adc: float,
    r_series_ohm: float = DEFAULT_NTC_R_SERIES,
    v_ref_v: float = DEFAULT_ADC_VREF,
) -> float:
    """Convert NTC high-side pullup divider voltage to thermistor resistance."""
    if v_adc <= 0.015:
        return 0.0  # Short-to-GND sentinel
    if v_adc >= (v_ref_v - 0.015):
        return 1e9  # Open-circuit sentinel
    return r_series_ohm * (v_adc / (v_ref_v - v_adc))


def steinhart_hart_celsius(
    r_ntc_ohm: float,
    a: float = DEFAULT_SH_A,
    b: float = DEFAULT_SH_B,
    c: float = DEFAULT_SH_C,
) -> Optional[float]:
    """Compute temperature in Celsius from NTC resistance using Steinhart-Hart."""
    if r_ntc_ohm <= 10.0 or r_ntc_ohm >= 1e7:
        return None
    ln_r = math.log(r_ntc_ohm)
    inv_t = a + b * ln_r + c * (ln_r ** 3)
    if inv_t <= 0.0:
        return None
    return (1.0 / inv_t) - 273.15


class ThermalDerivativeTracker:
    """Sliding-window OLS slope estimator for dT/dt thermal runaway detection."""

    def __init__(self, window_size: int = 16, num_channels: int = 4) -> None:
        self.window_size = window_size
        self.num_channels = num_channels
        self._history: List[Deque[Tuple[float, float]]] = [
            deque(maxlen=window_size) for _ in range(num_channels)
        ]

    def reset(self) -> None:
        for q in self._history:
            q.clear()

    def push(self, ch: int, temp_c: float, timestamp_s: float) -> float:
        """Push temperature sample (Celsius, timestamp in seconds) and return dT/dt in C/min."""
        if not (0 <= ch < self.num_channels):
            raise IndexError(f"NTC channel {ch} out of range 0..{self.num_channels - 1}")
        q = self._history[ch]
        q.append((timestamp_s, temp_c))
        return self.slope_c_per_min(ch)

    def slope_c_per_min(self, ch: int) -> float:
        q = self._history[ch]
        n = len(q)
        if n < 3 or (q[-1][0] - q[0][0]) < 4.0:
            return 0.0
        t0 = q[0][0]
        sum_t = 0.0
        sum_y = 0.0
        sum_tt = 0.0
        sum_ty = 0.0
        for ts, temp in q:
            t_min = (ts - t0) / 60.0
            sum_t += t_min
            sum_y += temp
            sum_tt += t_min * t_min
            sum_ty += t_min * temp
        denom = n * sum_tt - sum_t * sum_t
        if abs(denom) < 1e-9:
            return 0.0
        return (n * sum_ty - sum_t * sum_y) / denom


# ==============================================================================
# 21700 NMC/INR OCV-SoC Lookup Table & Pack Health Analytics
# ==============================================================================

def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)


def ocv_to_soc_percent(cell_ocv_v: float) -> float:
    """Piecewise-linear interpolation of 21700 NMC/INR OCV -> SoC (%)."""
    if cell_ocv_v <= OCV_LUT_21700[0][0]:
        return 0.0
    if cell_ocv_v >= OCV_LUT_21700[-1][0]:
        return 100.0
    for i in range(1, len(OCV_LUT_21700)):
        v0, s0 = OCV_LUT_21700[i - 1]
        v1, s1 = OCV_LUT_21700[i]
        if cell_ocv_v <= v1:
            t = (cell_ocv_v - v0) / (v1 - v0)
            return s0 + t * (s1 - s0)
    return 100.0


def soc_to_ocv_voltage(soc_percent: float) -> float:
    """Inverse 21700 SoC (%) -> cell OCV (V)."""
    soc = _clamp(soc_percent, 0.0, 100.0)
    if soc <= 0.0:
        return OCV_LUT_21700[0][0]
    if soc >= 100.0:
        return OCV_LUT_21700[-1][0]
    for i in range(1, len(OCV_LUT_21700)):
        v0, s0 = OCV_LUT_21700[i - 1]
        v1, s1 = OCV_LUT_21700[i]
        if soc <= s1:
            t = (soc - s0) / (s1 - s0)
            return v0 + t * (v1 - v0)
    return OCV_LUT_21700[-1][0]


def ocv_slope_volts_per_percent(soc_percent: float) -> float:
    s_lo = _clamp(soc_percent - 1.0, 0.0, 100.0)
    s_hi = _clamp(soc_percent + 1.0, 0.0, 100.0)
    if s_hi - s_lo < 0.1:
        return 0.01
    return (soc_to_ocv_voltage(s_hi) - soc_to_ocv_voltage(s_lo)) / (s_hi - s_lo)


@dataclass
class AlarmThresholds:
    cell_ov_warn_v: float = 4.21
    cell_ov_crit_v: float = 4.25
    cell_uv_warn_v: float = 3.00
    cell_uv_crit_v: float = 2.75
    cell_delta_warn_mv: float = 50.0
    cell_delta_crit_mv: float = 150.0
    max_discharge_a: float = 45.0
    max_charge_a: float = 15.0
    temp_warn_c: float = 50.0
    temp_crit_c: float = 60.0
    dtdt_warn_c_per_min: float = 2.0
    dtdt_crit_c_per_min: float = 5.0
    rdc_ratio_warn: float = 1.75
    tap_mismatch_max_v: float = 0.35


@dataclass
class PackConfiguration:
    series_cells: int = 4
    nominal_capacity_mah: float = 5000.0
    r_shunt_ohm: float = 0.001
    max_expected_a: float = 60.0
    r_dc_nominal_cell_mohm: float = 22.0
    alarms: AlarmThresholds = field(default_factory=AlarmThresholds)


@dataclass
class AlarmEvent:
    code: str
    severity: str  # "WARN" | "CRIT"
    message: str


@dataclass
class AnalyticsSnapshot:
    timestamp_s: float
    series_cells: int
    pack_voltage_v: float
    current_a: float
    power_w: float
    cell_voltages_v: List[float]
    cell_min_v: float
    cell_max_v: float
    cell_delta_mv: float
    temps_c: List[float]
    dtdt_c_per_min: List[float]
    temp_max_c: float
    dtdt_max_c_per_min: float
    soc_percent: float
    soc_ocv_est_percent: float
    soh_percent: float
    soh_capacity_percent: float
    soh_resistance_percent: float
    mah_discharged: float
    mah_charged: float
    wh_discharged: float
    wh_charged: float
    r_dc_pack_ohm: float
    r_dc_cell_mohm: float
    ocv_est_cell_v: float
    rest_seconds: float
    rdc_step_count: int
    alarms: List[AlarmEvent]
    alarm_codes: List[str]


class PackAnalyticsEngine:
    """Stateful battery pack analytics engine (OCV+Coulomb SoC, R_dc, SoH, Alarms)."""

    def __init__(self, config: Optional[PackConfiguration] = None) -> None:
        self.cfg = config or PackConfiguration()
        self.thermal_tracker = ThermalDerivativeTracker(window_size=16, num_channels=4)
        self.reset()

    def reset(self, initial_cell_v: Optional[float] = None) -> None:
        self.thermal_tracker.reset()
        self.soc_percent = 100.0 if initial_cell_v is None else ocv_to_soc_percent(initial_cell_v)
        self.soc_ocv_est_percent = self.soc_percent
        self.soh_capacity_percent = 100.0
        self.soh_resistance_percent = 100.0
        self.soh_percent = 100.0
        self.mah_discharged = 0.0
        self.mah_charged = 0.0
        self.wh_discharged = 0.0
        self.wh_charged = 0.0
        self.r_dc_cell_mohm = self.cfg.r_dc_nominal_cell_mohm
        self.r_dc_pack_ohm = (self.r_dc_cell_mohm / 1000.0) * self.cfg.series_cells
        self.ocv_est_cell_v = 4.20 if initial_cell_v is None else initial_cell_v
        self.rest_seconds = 0.0
        self.rdc_step_count = 0
        self.initialized = initial_cell_v is not None

        self._prev_timestamp_s: Optional[float] = None
        self._prev_current_a = 0.0
        self._prev_voltage_v = 0.0
        self._prev_power_w = 0.0
        self._step_ref_voltage_v = 0.0
        self._step_ref_current_a = 0.0
        self._step_timer_s = 0.0
        self._cycle_anchor_valid = False
        self._cycle_anchor_soc = 0.0
        self._cycle_anchor_mah = 0.0

    def update_thresholds(self, thresholds: AlarmThresholds) -> None:
        self.cfg.alarms = thresholds

    def _update_rdc_estimator(self, pack_voltage_v: float, current_a: float, dt_s: float) -> None:
        if dt_s <= 0.0:
            self._prev_voltage_v = pack_voltage_v
            self._step_ref_voltage_v = pack_voltage_v
            self._step_ref_current_a = current_a
            self._step_timer_s = 0.0
            return

        min_r = 0.002 * self.cfg.series_cells
        max_r = 0.500 * self.cfg.series_cells

        def _accept(dv: float, di: float) -> bool:
            if abs(di) < 1.0:
                return False
            r_meas_pack = -dv / di
            if min_r <= r_meas_pack <= max_r:
                alpha = 0.25
                if self.rdc_step_count == 0:
                    self.r_dc_pack_ohm = r_meas_pack
                else:
                    self.r_dc_pack_ohm = (1.0 - alpha) * self.r_dc_pack_ohm + alpha * r_meas_pack
                self.r_dc_cell_mohm = (self.r_dc_pack_ohm / self.cfg.series_cells) * 1000.0
                self.rdc_step_count += 1
                return True
            return False

        stepped = False
        if dt_s <= 2.5:
            stepped = _accept(pack_voltage_v - self._prev_voltage_v, current_a - self._prev_current_a)

        self._step_timer_s += dt_s
        if not stepped and self._step_timer_s <= 2.5:
            stepped = _accept(pack_voltage_v - self._step_ref_voltage_v, current_a - self._step_ref_current_a)

        if stepped or self._step_timer_s >= 2.0 or abs(current_a - self._prev_current_a) < 0.2:
            self._step_ref_voltage_v = pack_voltage_v
            self._step_ref_current_a = current_a
            self._step_timer_s = 0.0
        self._prev_voltage_v = pack_voltage_v

    def _update_soh(self) -> None:
        r_nom = self.cfg.r_dc_nominal_cell_mohm if self.cfg.r_dc_nominal_cell_mohm > 1.0 else 22.0
        r_ratio = self.r_dc_cell_mohm / r_nom
        soh_res = 100.0
        if r_ratio > 1.0:
            soh_res = _clamp(100.0 - 20.0 * (r_ratio - 1.0), 0.0, 100.0)
        self.soh_resistance_percent = soh_res
        self.soh_percent = _clamp(
            0.65 * self.soh_capacity_percent + 0.35 * self.soh_resistance_percent,
            0.0,
            100.0,
        )

    def evaluate_alarms(
        self,
        cell_voltages_v: List[float],
        pack_voltage_v: float,
        current_a: float,
        temps_c: List[float],
        dtdt_list: List[float],
        ina_hw_alert: bool = False,
    ) -> List[AlarmEvent]:
        alarms: List[AlarmEvent] = []
        lim = self.cfg.alarms

        if cell_voltages_v:
            c_min = min(cell_voltages_v)
            c_max = max(cell_voltages_v)
            c_delta_mv = (c_max - c_min) * 1000.0
            tap_sum = sum(cell_voltages_v)

            if c_max >= lim.cell_ov_crit_v:
                alarms.append(AlarmEvent("CELL_OV_CRIT", "CRIT", f"Cell max {c_max:.3f}V >= {lim.cell_ov_crit_v:.2f}V"))
            elif c_max >= lim.cell_ov_warn_v:
                alarms.append(AlarmEvent("CELL_OV_WARN", "WARN", f"Cell max {c_max:.3f}V >= {lim.cell_ov_warn_v:.2f}V"))

            if c_min <= lim.cell_uv_crit_v:
                alarms.append(AlarmEvent("CELL_UV_CRIT", "CRIT", f"Cell min {c_min:.3f}V <= {lim.cell_uv_crit_v:.2f}V"))
            elif c_min <= lim.cell_uv_warn_v:
                alarms.append(AlarmEvent("CELL_UV_WARN", "WARN", f"Cell min {c_min:.3f}V <= {lim.cell_uv_warn_v:.2f}V"))

            if c_delta_mv >= lim.cell_delta_crit_mv:
                alarms.append(AlarmEvent("CELL_DELTA_CRIT", "CRIT", f"Cell imbalance {c_delta_mv:.1f}mV >= {lim.cell_delta_crit_mv:.0f}mV"))
            elif c_delta_mv >= lim.cell_delta_warn_mv:
                alarms.append(AlarmEvent("CELL_DELTA_WARN", "WARN", f"Cell imbalance {c_delta_mv:.1f}mV >= {lim.cell_delta_warn_mv:.0f}mV"))

            if c_min < 0.50 or c_max > 4.60 or abs(tap_sum - pack_voltage_v) > lim.tap_mismatch_max_v:
                alarms.append(AlarmEvent("TAP_FAULT", "CRIT", f"Sense tap sum {tap_sum:.2f}V vs bus {pack_voltage_v:.2f}V mismatch"))

        if current_a >= lim.max_discharge_a:
            alarms.append(AlarmEvent("OC_DISCHARGE", "CRIT", f"Discharge current {current_a:.2f}A >= {lim.max_discharge_a:.1f}A"))
        elif current_a <= -lim.max_charge_a:
            alarms.append(AlarmEvent("OC_CHARGE", "CRIT", f"Charge current {abs(current_a):.2f}A >= {lim.max_charge_a:.1f}A"))

        valid_temps = [t for t in temps_c if t is not None and -40.0 <= t <= 150.0]
        if len(valid_temps) < len(temps_c):
            alarms.append(AlarmEvent("NTC_FAULT", "WARN", "One or more NTC probes disconnected or shorted"))

        if valid_temps:
            t_max = max(valid_temps)
            if t_max >= lim.temp_crit_c:
                alarms.append(AlarmEvent("TEMP_CRIT", "CRIT", f"Pack temp {t_max:.1f}C >= {lim.temp_crit_c:.1f}C"))
            elif t_max >= lim.temp_warn_c:
                alarms.append(AlarmEvent("TEMP_WARN", "WARN", f"Pack temp {t_max:.1f}C >= {lim.temp_warn_c:.1f}C"))

        if dtdt_list:
            slope_max = max(dtdt_list)
            if slope_max >= lim.dtdt_crit_c_per_min:
                alarms.append(AlarmEvent("THERMAL_RUNAWAY_CRIT", "CRIT", f"Thermal runaway dT/dt {slope_max:.2f} C/min >= {lim.dtdt_crit_c_per_min:.1f}"))
            elif slope_max >= lim.dtdt_warn_c_per_min:
                alarms.append(AlarmEvent("THERMAL_RUNAWAY_WARN", "WARN", f"Rapid heating dT/dt {slope_max:.2f} C/min >= {lim.dtdt_warn_c_per_min:.1f}"))

        if self.r_dc_cell_mohm >= lim.rdc_ratio_warn * self.cfg.r_dc_nominal_cell_mohm:
            alarms.append(AlarmEvent("HIGH_RDC", "WARN", f"Cell R_dc {self.r_dc_cell_mohm:.1f} mOhm exceeds {lim.rdc_ratio_warn:.2f}x nominal"))

        if ina_hw_alert:
            alarms.append(AlarmEvent("INA_HW_ALERT", "CRIT", "INA226 hardware ALERT pin latched"))

        return alarms

    def step(
        self,
        timestamp_s: float,
        pack_voltage_v: float,
        current_a: float,
        cell_voltages_v: Optional[List[float]] = None,
        temps_c: Optional[List[float]] = None,
        ina_hw_alert: bool = False,
    ) -> AnalyticsSnapshot:
        """Advance pack analytics by one sample frame."""
        n_cells = self.cfg.series_cells
        if not cell_voltages_v:
            v_avg = pack_voltage_v / n_cells
            cell_voltages_v = [v_avg] * n_cells
        else:
            n_cells = len(cell_voltages_v)

        if temps_c is None:
            temps_c = [25.0, 25.0, 25.0, 25.0]

        dt_s = 0.0 if self._prev_timestamp_s is None else max(0.0, timestamp_s - self._prev_timestamp_s)
        self._prev_timestamp_s = timestamp_s

        # Update thermal derivative tracker
        dtdt_list: List[float] = []
        for idx, t_val in enumerate(temps_c[:4]):
            if t_val is not None and -40.0 <= t_val <= 150.0:
                dtdt_list.append(self.thermal_tracker.push(idx, float(t_val), timestamp_s))
            else:
                dtdt_list.append(0.0)

        # Update R_dc load-step estimator
        self._update_rdc_estimator(pack_voltage_v, current_a, dt_s)

        v_cell_avg = sum(cell_voltages_v) / len(cell_voltages_v)
        r_cell_ohm = self.r_dc_cell_mohm / 1000.0
        v_ocv_est = v_cell_avg + current_a * r_cell_ohm
        soc_ocv = ocv_to_soc_percent(v_ocv_est)
        self.ocv_est_cell_v = v_ocv_est
        self.soc_ocv_est_percent = soc_ocv

        if not self.initialized:
            self.soc_percent = soc_ocv
            self.initialized = True
            self._prev_current_a = current_a
            self._prev_power_w = pack_voltage_v * current_a
            self._cycle_anchor_valid = abs(current_a) < 0.20
            self._cycle_anchor_soc = soc_ocv
            self._cycle_anchor_mah = 0.0

        if dt_s > 0.0:
            dt_h = dt_s / 3600.0
            i_mid = 0.5 * (self._prev_current_a + current_a)
            p_now = pack_voltage_v * current_a
            p_mid = 0.5 * (self._prev_power_w + p_now)
            d_mah = i_mid * dt_h * 1000.0
            d_wh = p_mid * dt_h

            if d_mah >= 0.0:
                self.mah_discharged += d_mah
                self.wh_discharged += d_wh
            else:
                self.mah_charged += -d_mah
                self.wh_charged += -d_wh

            eff_cap = self.cfg.nominal_capacity_mah * (self.soh_capacity_percent / 100.0)
            safe_cap = eff_cap if eff_cap > 100.0 else self.cfg.nominal_capacity_mah
            soc_coulomb = _clamp(self.soc_percent - (d_mah / safe_cap) * 100.0, 0.0, 100.0)

            if abs(current_a) < 0.15:
                self.rest_seconds += dt_s
            else:
                self.rest_seconds = 0.0

            alpha_ocv = 0.0
            dv_dsoc = ocv_slope_volts_per_percent(soc_coulomb)
            slope_factor = _clamp(dv_dsoc / 0.012, 0.15, 1.0)

            if self.rest_seconds >= 30.0:
                alpha_ocv = _clamp(0.05 * slope_factor * _clamp(dt_s, 0.1, 2.0), 0.0, 0.15)
                if self._cycle_anchor_valid:
                    net_mah = (self.mah_discharged - self.mah_charged) - self._cycle_anchor_mah
                    dsoc = self._cycle_anchor_soc - soc_ocv
                    if dsoc >= 40.0 and net_mah > 0.0:
                        q_est_mah = net_mah / (dsoc / 100.0)
                        new_soh_cap = _clamp((q_est_mah / self.cfg.nominal_capacity_mah) * 100.0, 0.0, 100.0)
                        self.soh_capacity_percent = 0.5 * self.soh_capacity_percent + 0.5 * new_soh_cap
                        self._cycle_anchor_soc = soc_ocv
                        self._cycle_anchor_mah = self.mah_discharged - self.mah_charged
                else:
                    self._cycle_anchor_valid = True
                    self._cycle_anchor_soc = soc_ocv
                    self._cycle_anchor_mah = self.mah_discharged - self.mah_charged
            elif abs(current_a) < 0.05 * (self.cfg.nominal_capacity_mah / 1000.0):
                alpha_ocv = 0.005 * slope_factor

            self.soc_percent = _clamp((1.0 - alpha_ocv) * soc_coulomb + alpha_ocv * soc_ocv, 0.0, 100.0)
            self._prev_current_a = current_a
            self._prev_power_w = p_now

        self._update_soh()
        alarms = self.evaluate_alarms(cell_voltages_v, pack_voltage_v, current_a, temps_c, dtdt_list, ina_hw_alert)

        c_min = min(cell_voltages_v)
        c_max = max(cell_voltages_v)
        return AnalyticsSnapshot(
            timestamp_s=timestamp_s,
            series_cells=n_cells,
            pack_voltage_v=pack_voltage_v,
            current_a=current_a,
            power_w=pack_voltage_v * current_a,
            cell_voltages_v=list(cell_voltages_v),
            cell_min_v=c_min,
            cell_max_v=c_max,
            cell_delta_mv=(c_max - c_min) * 1000.0,
            temps_c=list(temps_c),
            dtdt_c_per_min=dtdt_list,
            temp_max_c=max(temps_c) if temps_c else 25.0,
            dtdt_max_c_per_min=max(dtdt_list) if dtdt_list else 0.0,
            soc_percent=self.soc_percent,
            soc_ocv_est_percent=self.soc_ocv_est_percent,
            soh_percent=self.soh_percent,
            soh_capacity_percent=self.soh_capacity_percent,
            soh_resistance_percent=self.soh_resistance_percent,
            mah_discharged=self.mah_discharged,
            mah_charged=self.mah_charged,
            wh_discharged=self.wh_discharged,
            wh_charged=self.wh_charged,
            r_dc_pack_ohm=self.r_dc_pack_ohm,
            r_dc_cell_mohm=self.r_dc_cell_mohm,
            ocv_est_cell_v=self.ocv_est_cell_v,
            rest_seconds=self.rest_seconds,
            rdc_step_count=self.rdc_step_count,
            alarms=alarms,
            alarm_codes=[a.code for a in alarms],
        )
