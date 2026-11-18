export interface AlarmItem {
  code: string;
  severity: "WARN" | "CRIT" | "INFO";
  message: string;
}

export interface AlarmLogRow {
  id: number;
  session_id: string;
  timestamp_s: number;
  code: string;
  severity: string;
  message: string;
  acknowledged: number;
  created_at: string;
}

export interface TelemetrySample {
  id?: number;
  session_id?: string;
  timestamp_s: number;
  series_cells: number;
  pack_voltage_v: number;
  current_a: number;
  power_w: number;
  cell_voltages_v: number[];
  cell_min_v: number;
  cell_max_v: number;
  cell_delta_mv: number;
  temps_c: number[];
  dtdt_c_per_min: number[];
  temp_max_c: number;
  dtdt_max_c_per_min: number;
  soc_percent: number;
  soc_ocv_est_percent: number;
  soh_percent: number;
  soh_capacity_percent: number;
  soh_resistance_percent: number;
  mah_discharged: number;
  wh_discharged: number;
  r_dc_pack_ohm: number;
  r_dc_cell_mohm: number;
  ocv_est_cell_v: number;
  rest_seconds: number;
  rdc_step_count: number;
  alarms: AlarmItem[];
  alarm_codes: string[];
}

export interface DatasetMeta {
  id: string;
  title: string;
  series_cells: number;
  nominal_capacity_mah: number;
  r_dc_nominal_cell_mohm: number;
  description: string;
}

export interface SessionInfo {
  session_id: string;
  title: string;
  dataset_id: string | null;
  series_cells: number;
  nominal_capacity_mah: number;
  r_dc_nominal_cell_mohm: number;
  created_at: string;
  sample_count: number;
}

export interface AlarmThresholds {
  cell_ov_warn_v: number;
  cell_ov_crit_v: number;
  cell_uv_warn_v: number;
  cell_uv_crit_v: number;
  cell_delta_warn_mv: number;
  cell_delta_crit_mv: number;
  max_discharge_a: number;
  max_charge_a: number;
  temp_warn_c: number;
  temp_crit_c: number;
  dtdt_warn_c_per_min: number;
  dtdt_crit_c_per_min: number;
  rdc_ratio_warn: number;
  tap_mismatch_max_v: number;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  active_session_id: string;
  safety: {
    monitor_only: boolean;
    balancing_supported: boolean;
    charging_supported: boolean;
    fet_switching_supported: boolean;
    requires_external_bms_and_fuse: boolean;
  };
}

export interface CalibrationCalcRequest {
  r_shunt_mohm: number;
  max_expected_current_a: number;
  series_cells: number;
  nominal_capacity_mah: number;
  current_meas1: number;
  current_ref1: number;
  current_meas2: number;
  current_ref2: number;
  vbus_meas1: number;
  vbus_ref1: number;
  vbus_meas2: number;
  vbus_ref2: number;
  tap_channel: number;
  tap_meas1: number;
  tap_ref1: number;
  tap_meas2: number;
  tap_ref2: number;
}

export interface CalibrationCalcResponse {
  ina226: {
    r_shunt_ohm: number;
    max_expected_current_a: number;
    ideal_current_lsb_a: number;
    cal_register: number;
    cal_register_hex: string;
    effective_current_lsb_a: number;
    power_lsb_w: number;
    full_scale_shunt_mv: number;
    within_81_92mv_limit: boolean;
  };
  current_calibration: { gain: number; offset_a: number };
  vbus_calibration: { gain: number; offset_v: number };
  tap_calibration: {
    channel: number;
    divider_ratio: number;
    gain: number;
    offset_v: number;
  };
  esp32_cli_commands: string[];
}
