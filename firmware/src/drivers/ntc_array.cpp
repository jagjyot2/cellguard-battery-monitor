#include "drivers/ntc_array.h"

#include <Arduino.h>
#include <math.h>

namespace cellguard {

NTCArray::NTCArray(const uint8_t pins[NUM_NTC_CHANNELS], float r_series_ohm, float v_ref_v)
    : r_series_ohm_(r_series_ohm), v_ref_v_(v_ref_v) {
    for (uint8_t i = 0; i < NUM_NTC_CHANNELS; ++i) {
        pins_[i] = pins[i];
    }
}

void NTCArray::begin() {
    analogReadResolution(12);
    for (uint8_t i = 0; i < NUM_NTC_CHANNELS; ++i) {
        pinMode(pins_[i], INPUT);
        analogSetPinAttenuation(pins_[i], ADC_11db);
    }
}

void NTCArray::setSteinhartHart(float a, float b, float c) {
    sh_a_ = a;
    sh_b_ = b;
    sh_c_ = c;
}

float NTCArray::voltageToResistance(float v_adc) const {
    // High-side series pullup R_series to V_ref, NTC to GND:
    // V_adc = V_ref * (R_ntc / (R_series + R_ntc)) => R_ntc = R_series * V_adc / (V_ref - V_adc)
    if (v_adc <= 0.015f) {
        return 0.0f;  // Short-to-GND fault sentinel
    }
    if (v_adc >= (v_ref_v_ - 0.015f)) {
        return 1e9f;  // Open-circuit fault sentinel
    }
    return r_series_ohm_ * (v_adc / (v_ref_v_ - v_adc));
}

float NTCArray::resistanceToCelsius(float r_ntc_ohm) const {
    if (r_ntc_ohm <= 10.0f || r_ntc_ohm >= 1e7f) {
        return NAN;
    }
    const float ln_r = logf(r_ntc_ohm);
    const float inv_t = sh_a_ + sh_b_ * ln_r + sh_c_ * (ln_r * ln_r * ln_r);
    if (inv_t <= 0.0f) {
        return NAN;
    }
    return (1.0f / inv_t) - 273.15f;
}

void NTCArray::pushSample(uint8_t ch, float temp_c, uint32_t now_ms) {
    if (ch >= NUM_NTC_CHANNELS || isnan(temp_c)) {
        return;
    }
    const uint8_t idx = hist_head_[ch];
    temp_hist_[ch][idx] = temp_c;
    time_hist_ms_[ch][idx] = now_ms;
    hist_head_[ch] = (idx + 1) % HISTORY_WINDOW;
    if (hist_count_[ch] < HISTORY_WINDOW) {
        hist_count_[ch]++;
    }
}

float NTCArray::computeSlopeCPerMin(uint8_t ch) const {
    if (ch >= NUM_NTC_CHANNELS || hist_count_[ch] < 3) {
        return 0.0f;
    }
    const uint8_t n = hist_count_[ch];
    // Oldest entry sits at (head - count + WINDOW) % WINDOW
    const uint8_t start = (hist_head_[ch] + HISTORY_WINDOW - n) % HISTORY_WINDOW;
    const uint8_t newest = (hist_head_[ch] + HISTORY_WINDOW - 1) % HISTORY_WINDOW;
    const uint32_t t0 = time_hist_ms_[ch][start];
    if ((time_hist_ms_[ch][newest] - t0) < 4000u) {
        return 0.0f;  // Require >= 4s window before emitting derivative alarm
    }

    double sum_t = 0.0;
    double sum_y = 0.0;
    double sum_tt = 0.0;
    double sum_ty = 0.0;

    for (uint8_t k = 0; k < n; ++k) {
        const uint8_t idx = (start + k) % HISTORY_WINDOW;
        const double t_min = static_cast<double>(time_hist_ms_[ch][idx] - t0) / 60000.0;
        const double y = static_cast<double>(temp_hist_[ch][idx]);
        sum_t += t_min;
        sum_y += y;
        sum_tt += t_min * t_min;
        sum_ty += t_min * y;
    }
    const double dn = static_cast<double>(n);
    const double denom = dn * sum_tt - sum_t * sum_t;
    if (fabs(denom) < 1e-9) {
        return 0.0f;
    }
    return static_cast<float>((dn * sum_ty - sum_t * sum_y) / denom);
}

float NTCArray::readPinVoltage(uint8_t pin) const {
    uint32_t mv_sum = 0;
    constexpr uint8_t SAMPLES = 16;
    for (uint8_t i = 0; i < SAMPLES; ++i) {
        mv_sum += analogReadMilliVolts(pin);
    }
    return (static_cast<float>(mv_sum) / static_cast<float>(SAMPLES)) / 1000.0f;
}

NTCArraySummary NTCArray::sampleAll(uint32_t now_ms, const AlarmThresholds& limits) {
    NTCArraySummary summary{};
    summary.max_temp_c = -100.0f;
    summary.min_temp_c = 200.0f;
    summary.max_dtdt_c_per_min = 0.0f;

    for (uint8_t ch = 0; ch < NUM_NTC_CHANNELS; ++ch) {
        NTCChannelStatus& st = summary.channels[ch];
        const float v_adc = readPinVoltage(pins_[ch]);
        const float r_ntc = voltageToResistance(v_adc);
        const float temp_c = resistanceToCelsius(r_ntc);

        st.resistance_ohm = r_ntc;
        if (isnan(temp_c) || temp_c < -40.0f || temp_c > 150.0f) {
            st.sensor_fault = true;
            st.temp_c = 0.0f;
            st.dt_dt_c_per_min = 0.0f;
            summary.any_sensor_fault = true;
            continue;
        }

        pushSample(ch, temp_c, now_ms);
        st.temp_c = temp_c;
        st.dt_dt_c_per_min = computeSlopeCPerMin(ch);
        st.warn_overtemp = (temp_c >= limits.temp_warn_c);
        st.crit_overtemp = (temp_c >= limits.temp_crit_c);
        st.warn_runaway  = (st.dt_dt_c_per_min >= limits.dtdt_warn_c_per_min);
        st.crit_runaway  = (st.dt_dt_c_per_min >= limits.dtdt_crit_c_per_min);

        if (temp_c > summary.max_temp_c) summary.max_temp_c = temp_c;
        if (temp_c < summary.min_temp_c) summary.min_temp_c = temp_c;
        if (st.dt_dt_c_per_min > summary.max_dtdt_c_per_min) {
            summary.max_dtdt_c_per_min = st.dt_dt_c_per_min;
        }
        summary.any_overtemp_warn |= st.warn_overtemp;
        summary.any_overtemp_crit |= st.crit_overtemp;
        summary.any_runaway_warn  |= st.warn_runaway;
        summary.any_runaway_crit  |= st.crit_runaway;
    }

    if (summary.max_temp_c < -90.0f) {
        summary.max_temp_c = 0.0f;
        summary.min_temp_c = 0.0f;
    }
    return summary;
}

}  // namespace cellguard
