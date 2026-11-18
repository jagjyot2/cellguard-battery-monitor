#pragma once

#include <stdint.h>
#include "cellguard_config.h"
#include "drivers/cell_tap_monitor.h"
#include "drivers/ntc_array.h"

namespace cellguard {

enum AlarmBits : uint32_t {
    ALARM_NONE             = 0,
    ALARM_CELL_OV_WARN     = 1u << 0,
    ALARM_CELL_OV_CRIT     = 1u << 1,
    ALARM_CELL_UV_WARN     = 1u << 2,
    ALARM_CELL_UV_CRIT     = 1u << 3,
    ALARM_CELL_DELTA_WARN  = 1u << 4,
    ALARM_CELL_DELTA_CRIT  = 1u << 5,
    ALARM_OC_DISCHARGE     = 1u << 6,
    ALARM_OC_CHARGE        = 1u << 7,
    ALARM_TEMP_WARN        = 1u << 8,
    ALARM_TEMP_CRIT        = 1u << 9,
    ALARM_RUNAWAY_WARN     = 1u << 10,
    ALARM_RUNAWAY_CRIT     = 1u << 11,
    ALARM_HIGH_RDC         = 1u << 12,
    ALARM_TAP_FAULT        = 1u << 13,
    ALARM_NTC_FAULT        = 1u << 14,
    ALARM_INA_HW_ALERT     = 1u << 15,
};

struct AnalyticsState {
    float    soc_percent           = 100.0f;
    float    soc_ocv_est_percent   = 100.0f;
    float    soh_percent           = 100.0f;
    float    soh_capacity_percent  = 100.0f;
    float    soh_resistance_percent = 100.0f;
    float    mah_discharged        = 0.0f;
    float    mah_charged           = 0.0f;
    float    wh_discharged         = 0.0f;
    float    wh_charged            = 0.0f;
    float    r_dc_pack_ohm         = 0.088f;
    float    r_dc_cell_mohm        = 22.0f;
    float    ocv_est_cell_v        = 4.20f;
    float    rest_seconds          = 0.0f;
    uint32_t rdc_step_count        = 0;
    uint32_t alarm_mask            = ALARM_NONE;
    bool     initialized           = false;
};

class BatteryAnalytics {
public:
    explicit BatteryAnalytics(const PackConfig& cfg);

    void updateConfig(const PackConfig& cfg);
    void resetSession(float initial_cell_v = -1.0f);

    // 21700 NMC/INR OCV-SoC lookup table & sensitivity
    static float ocvToSocPercent(float cell_ocv_v);
    static float socToOcvVoltage(float soc_percent);
    static float ocvSlopeVoltsPerPercent(float soc_percent);

    // Main step update (dt_s in seconds, positive current_a = discharge)
    const AnalyticsState& update(
        float pack_voltage_v,
        float current_a,
        float dt_s,
        const CellTapSnapshot& taps,
        const NTCArraySummary& thermals,
        bool ina_hw_alert = false);

    const AnalyticsState& state() const { return state_; }

private:
    PackConfig     cfg_;
    AnalyticsState state_{};

    float prev_current_a_     = 0.0f;
    float prev_voltage_v_     = 0.0f;
    float prev_power_w_       = 0.0f;
    float step_ref_voltage_v_ = 0.0f;
    float step_ref_current_a_ = 0.0f;
    float step_timer_s_       = 0.0f;

    // Deep-cycle capacity estimation anchors
    bool  cycle_anchor_valid_ = false;
    float cycle_anchor_soc_   = 0.0f;
    float cycle_anchor_mah_   = 0.0f;

    void evaluateAlarms(const CellTapSnapshot& taps, const NTCArraySummary& thermals, float current_a, bool ina_hw_alert);
    void updateRdcEstimator(float pack_voltage_v, float current_a, float dt_s);
    void updateSohEstimate();
};

}  // namespace cellguard
