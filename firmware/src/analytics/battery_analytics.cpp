#include "analytics/battery_analytics.h"

#include <math.h>

namespace cellguard {

namespace {

struct OcvPoint {
    float ocv_v;
    float soc_pct;
};

// Calibrated 21700 NMC/INR open-circuit voltage profile (Samsung 50E / Molicel P42A / LG M50T class)
constexpr OcvPoint k21700OcvLut[] = {
    {2.50f,   0.0f},
    {2.80f,   1.5f},
    {3.00f,   3.5f},
    {3.15f,   6.0f},
    {3.25f,  10.0f},
    {3.35f,  16.0f},
    {3.42f,  22.0f},
    {3.48f,  28.0f},
    {3.53f,  35.0f},
    {3.58f,  42.0f},
    {3.63f,  50.0f},
    {3.69f,  58.0f},
    {3.76f,  66.0f},
    {3.84f,  74.0f},
    {3.92f,  82.0f},
    {4.00f,  89.0f},
    {4.07f,  94.0f},
    {4.14f,  98.0f},
    {4.20f, 100.0f},
};

constexpr int kLutSize = sizeof(k21700OcvLut) / sizeof(k21700OcvLut[0]);

inline float clampf(float x, float lo, float hi) {
    return (x < lo) ? lo : ((x > hi) ? hi : x);
}

}  // namespace

BatteryAnalytics::BatteryAnalytics(const PackConfig& cfg) : cfg_(cfg) {
    state_.r_dc_cell_mohm = cfg_.r_dc_nominal_cell_mohm;
    state_.r_dc_pack_ohm  = (cfg_.r_dc_nominal_cell_mohm / 1000.0f) * static_cast<float>(cfg_.series_cells);
}

void BatteryAnalytics::updateConfig(const PackConfig& cfg) {
    cfg_ = cfg;
}

void BatteryAnalytics::resetSession(float initial_cell_v) {
    state_ = AnalyticsState{};
    state_.r_dc_cell_mohm = cfg_.r_dc_nominal_cell_mohm;
    state_.r_dc_pack_ohm  = (cfg_.r_dc_nominal_cell_mohm / 1000.0f) * static_cast<float>(cfg_.series_cells);
    if (initial_cell_v > 0.5f) {
        state_.soc_percent         = ocvToSocPercent(initial_cell_v);
        state_.soc_ocv_est_percent = state_.soc_percent;
        state_.ocv_est_cell_v      = initial_cell_v;
        state_.initialized         = true;
    }
    cycle_anchor_valid_ = false;
    prev_current_a_     = 0.0f;
    prev_voltage_v_     = 0.0f;
    prev_power_w_       = 0.0f;
    step_timer_s_       = 0.0f;
}

float BatteryAnalytics::ocvToSocPercent(float cell_ocv_v) {
    if (cell_ocv_v <= k21700OcvLut[0].ocv_v) return 0.0f;
    if (cell_ocv_v >= k21700OcvLut[kLutSize - 1].ocv_v) return 100.0f;

    for (int i = 1; i < kLutSize; ++i) {
        if (cell_ocv_v <= k21700OcvLut[i].ocv_v) {
            const float v0 = k21700OcvLut[i - 1].ocv_v;
            const float v1 = k21700OcvLut[i].ocv_v;
            const float s0 = k21700OcvLut[i - 1].soc_pct;
            const float s1 = k21700OcvLut[i].soc_pct;
            const float t  = (cell_ocv_v - v0) / (v1 - v0);
            return s0 + t * (s1 - s0);
        }
    }
    return 100.0f;
}

float BatteryAnalytics::socToOcvVoltage(float soc_percent) {
    const float soc = clampf(soc_percent, 0.0f, 100.0f);
    if (soc <= 0.0f) return k21700OcvLut[0].ocv_v;
    if (soc >= 100.0f) return k21700OcvLut[kLutSize - 1].ocv_v;

    for (int i = 1; i < kLutSize; ++i) {
        if (soc <= k21700OcvLut[i].soc_pct) {
            const float s0 = k21700OcvLut[i - 1].soc_pct;
            const float s1 = k21700OcvLut[i].soc_pct;
            const float v0 = k21700OcvLut[i - 1].ocv_v;
            const float v1 = k21700OcvLut[i].ocv_v;
            const float t  = (soc - s0) / (s1 - s0);
            return v0 + t * (v1 - v0);
        }
    }
    return k21700OcvLut[kLutSize - 1].ocv_v;
}

float BatteryAnalytics::ocvSlopeVoltsPerPercent(float soc_percent) {
    const float s_lo = clampf(soc_percent - 1.0f, 0.0f, 100.0f);
    const float s_hi = clampf(soc_percent + 1.0f, 0.0f, 100.0f);
    if (s_hi - s_lo < 0.1f) return 0.01f;
    return (socToOcvVoltage(s_hi) - socToOcvVoltage(s_lo)) / (s_hi - s_lo);
}

void BatteryAnalytics::updateRdcEstimator(float pack_voltage_v, float current_a, float dt_s) {
    if (dt_s <= 0.0f) {
        prev_voltage_v_     = pack_voltage_v;
        step_ref_voltage_v_ = pack_voltage_v;
        step_ref_current_a_ = current_a;
        step_timer_s_       = 0.0f;
        return;
    }

    const float min_pack_r = 0.002f * static_cast<float>(cfg_.series_cells);
    const float max_pack_r = 0.500f * static_cast<float>(cfg_.series_cells);

    auto accept_measurement = [&](float dv, float di) -> bool {
        if (fabsf(di) < 1.0f) return false;
        const float r_meas_pack = -dv / di;
        if (r_meas_pack >= min_pack_r && r_meas_pack <= max_pack_r) {
            constexpr float alpha = 0.25f;
            if (state_.rdc_step_count == 0) {
                state_.r_dc_pack_ohm = r_meas_pack;
            } else {
                state_.r_dc_pack_ohm = (1.0f - alpha) * state_.r_dc_pack_ohm + alpha * r_meas_pack;
            }
            state_.r_dc_cell_mohm = (state_.r_dc_pack_ohm / static_cast<float>(cfg_.series_cells)) * 1000.0f;
            state_.rdc_step_count++;
            return true;
        }
        return false;
    };

    // 1) Check immediate sample-to-sample step within <= 2.5s
    bool stepped = false;
    if (dt_s <= 2.5f) {
        stepped = accept_measurement(pack_voltage_v - prev_voltage_v_, current_a - prev_current_a_);
    }

    // 2) Otherwise check against 2.5s rolling reference baseline
    step_timer_s_ += dt_s;
    if (!stepped && step_timer_s_ <= 2.5f) {
        stepped = accept_measurement(pack_voltage_v - step_ref_voltage_v_, current_a - step_ref_current_a_);
    }

    if (stepped || step_timer_s_ >= 2.0f || fabsf(current_a - prev_current_a_) < 0.2f) {
        step_ref_voltage_v_ = pack_voltage_v;
        step_ref_current_a_ = current_a;
        step_timer_s_       = 0.0f;
    }
    prev_voltage_v_ = pack_voltage_v;
}

void BatteryAnalytics::updateSohEstimate() {
    // Resistance-growth SoH: 100% at <= nominal R_dc, 80% at 2.0x nominal R_dc
    const float r_nom = (cfg_.r_dc_nominal_cell_mohm > 1.0f) ? cfg_.r_dc_nominal_cell_mohm : 22.0f;
    const float r_ratio = state_.r_dc_cell_mohm / r_nom;
    float soh_res = 100.0f;
    if (r_ratio > 1.0f) {
        soh_res = clampf(100.0f - 20.0f * (r_ratio - 1.0f), 0.0f, 100.0f);
    }
    state_.soh_resistance_percent = soh_res;
    state_.soh_percent = clampf(
        0.65f * state_.soh_capacity_percent + 0.35f * state_.soh_resistance_percent,
        0.0f,
        100.0f
    );
}

void BatteryAnalytics::evaluateAlarms(
    const CellTapSnapshot& taps,
    const NTCArraySummary& thermals,
    float current_a,
    bool ina_hw_alert) {

    uint32_t mask = ALARM_NONE;
    const AlarmThresholds& lim = cfg_.alarms;

    if (taps.valid) {
        if (taps.cell_max_v >= lim.cell_ov_crit_v) mask |= ALARM_CELL_OV_CRIT;
        else if (taps.cell_max_v >= lim.cell_ov_warn_v) mask |= ALARM_CELL_OV_WARN;

        if (taps.cell_min_v <= lim.cell_uv_crit_v) mask |= ALARM_CELL_UV_CRIT;
        else if (taps.cell_min_v <= lim.cell_uv_warn_v) mask |= ALARM_CELL_UV_WARN;

        if (taps.cell_delta_mv >= lim.cell_delta_crit_mv) mask |= ALARM_CELL_DELTA_CRIT;
        else if (taps.cell_delta_mv >= lim.cell_delta_warn_mv) mask |= ALARM_CELL_DELTA_WARN;

        if (taps.tap_fault) mask |= ALARM_TAP_FAULT;
    }

    if (current_a >= lim.max_discharge_a) mask |= ALARM_OC_DISCHARGE;
    if (current_a <= -lim.max_charge_a)   mask |= ALARM_OC_CHARGE;

    if (thermals.any_overtemp_crit) mask |= ALARM_TEMP_CRIT;
    else if (thermals.any_overtemp_warn) mask |= ALARM_TEMP_WARN;

    if (thermals.any_runaway_crit) mask |= ALARM_RUNAWAY_CRIT;
    else if (thermals.any_runaway_warn) mask |= ALARM_RUNAWAY_WARN;

    if (thermals.any_sensor_fault) mask |= ALARM_NTC_FAULT;

    if (state_.r_dc_cell_mohm >= lim.rdc_ratio_warn * cfg_.r_dc_nominal_cell_mohm) {
        mask |= ALARM_HIGH_RDC;
    }
    if (ina_hw_alert) {
        mask |= ALARM_INA_HW_ALERT;
    }
    state_.alarm_mask = mask;
}

const AnalyticsState& BatteryAnalytics::update(
    float pack_voltage_v,
    float current_a,
    float dt_s,
    const CellTapSnapshot& taps,
    const NTCArraySummary& thermals,
    bool ina_hw_alert) {

    const uint8_t n_cells = (cfg_.series_cells > 0) ? cfg_.series_cells : 4;
    const float v_cell_avg = (taps.valid && taps.cell_min_v > 0.5f)
        ? (taps.pack_sum_v / static_cast<float>(n_cells))
        : (pack_voltage_v / static_cast<float>(n_cells));

    // Update dynamic DC internal resistance estimator before OCV IR compensation
    updateRdcEstimator(pack_voltage_v, current_a, dt_s);

    const float r_cell_ohm = state_.r_dc_cell_mohm / 1000.0f;
    const float v_ocv_est  = v_cell_avg + current_a * r_cell_ohm;
    const float soc_ocv    = ocvToSocPercent(v_ocv_est);
    state_.ocv_est_cell_v      = v_ocv_est;
    state_.soc_ocv_est_percent = soc_ocv;

    if (!state_.initialized) {
        state_.soc_percent = soc_ocv;
        state_.initialized = true;
        prev_current_a_    = current_a;
        prev_power_w_      = pack_voltage_v * current_a;
        cycle_anchor_valid_ = (fabsf(current_a) < 0.20f);
        cycle_anchor_soc_   = soc_ocv;
        cycle_anchor_mah_   = 0.0f;
    }

    // Trapezoidal Coulomb & Energy integration
    if (dt_s > 0.0f) {
        const float dt_h      = dt_s / 3600.0f;
        const float i_mid     = 0.5f * (prev_current_a_ + current_a);
        const float p_now     = pack_voltage_v * current_a;
        const float p_mid     = 0.5f * (prev_power_w_ + p_now);
        const float d_mah     = i_mid * dt_h * 1000.0f;
        const float d_wh      = p_mid * dt_h;

        if (d_mah >= 0.0f) {
            state_.mah_discharged += d_mah;
            state_.wh_discharged  += d_wh;
        } else {
            state_.mah_charged += (-d_mah);
            state_.wh_charged  += (-d_wh);
        }

        const float eff_cap_mah = cfg_.nominal_capacity_mah * (state_.soh_capacity_percent / 100.0f);
        const float safe_cap    = (eff_cap_mah > 100.0f) ? eff_cap_mah : cfg_.nominal_capacity_mah;
        const float soc_coulomb = clampf(state_.soc_percent - (d_mah / safe_cap) * 100.0f, 0.0f, 100.0f);

        // Rest detection for OCV fusion & capacity-fade anchor update
        if (fabsf(current_a) < 0.15f) {
            state_.rest_seconds += dt_s;
        } else {
            state_.rest_seconds = 0.0f;
        }

        // Complementary fusion gain: strong during settled rest & steep OCV knees, near zero under active load
        float alpha_ocv = 0.0f;
        const float dv_dsoc = ocvSlopeVoltsPerPercent(soc_coulomb);
        const float slope_factor = clampf(dv_dsoc / 0.012f, 0.15f, 1.0f);

        if (state_.rest_seconds >= 30.0f) {
            alpha_ocv = clampf(0.05f * slope_factor * clampf(dt_s, 0.1f, 2.0f), 0.0f, 0.15f);
            if (cycle_anchor_valid_) {
                const float net_mah = (state_.mah_discharged - state_.mah_charged) - cycle_anchor_mah_;
                const float dsoc = cycle_anchor_soc_ - soc_ocv;
                if (dsoc >= 40.0f && net_mah > 0.0f) {
                    const float q_est_mah = net_mah / (dsoc / 100.0f);
                    const float new_soh_cap = clampf((q_est_mah / cfg_.nominal_capacity_mah) * 100.0f, 0.0f, 100.0f);
                    state_.soh_capacity_percent = 0.5f * state_.soh_capacity_percent + 0.5f * new_soh_cap;
                    cycle_anchor_soc_ = soc_ocv;
                    cycle_anchor_mah_ = state_.mah_discharged - state_.mah_charged;
                }
            } else {
                cycle_anchor_valid_ = true;
                cycle_anchor_soc_   = soc_ocv;
                cycle_anchor_mah_   = state_.mah_discharged - state_.mah_charged;
            }
        } else if (fabsf(current_a) < 0.05f * (cfg_.nominal_capacity_mah / 1000.0f)) {
            alpha_ocv = 0.005f * slope_factor;
        }

        state_.soc_percent = clampf((1.0f - alpha_ocv) * soc_coulomb + alpha_ocv * soc_ocv, 0.0f, 100.0f);
        prev_current_a_ = current_a;
        prev_power_w_   = p_now;
    }

    updateSohEstimate();
    evaluateAlarms(taps, thermals, current_a, ina_hw_alert);
    return state_;
}

}  // namespace cellguard
