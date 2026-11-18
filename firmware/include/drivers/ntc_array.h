#pragma once

#include <stdint.h>
#include "cellguard_config.h"

namespace cellguard {

struct NTCChannelStatus {
    float temp_c           = 25.0f;
    float dt_dt_c_per_min  = 0.0f;
    float resistance_ohm   = 10000.0f;
    bool  sensor_fault     = false;
    bool  warn_overtemp    = false;
    bool  crit_overtemp    = false;
    bool  warn_runaway     = false;
    bool  crit_runaway     = false;
};

struct NTCArraySummary {
    NTCChannelStatus channels[NUM_NTC_CHANNELS]{};
    float max_temp_c           = 25.0f;
    float min_temp_c           = 25.0f;
    float max_dtdt_c_per_min   = 0.0f;
    bool  any_sensor_fault     = false;
    bool  any_overtemp_warn    = false;
    bool  any_overtemp_crit    = false;
    bool  any_runaway_warn     = false;
    bool  any_runaway_crit     = false;
};

class NTCArray {
public:
    static constexpr uint8_t HISTORY_WINDOW = 16;

    // Standard 10k @ 25C NTC (Murata NCP18XH103 / Semitec 103AT-2)
    static constexpr float DEFAULT_SH_A = 1.129148e-3f;
    static constexpr float DEFAULT_SH_B = 2.34125e-4f;
    static constexpr float DEFAULT_SH_C = 8.76741e-8f;
    static constexpr float DEFAULT_R_SERIES = 10000.0f;

    NTCArray(const uint8_t pins[NUM_NTC_CHANNELS],
             float r_series_ohm = DEFAULT_R_SERIES,
             float v_ref_v = ADC_VREF_DEFAULT_V);

    void begin();
    void setSteinhartHart(float a, float b, float c);

    // Pure math helpers
    float voltageToResistance(float v_adc) const;
    float resistanceToCelsius(float r_ntc_ohm) const;
    float computeSlopeCPerMin(uint8_t ch) const;

    // Acquire all 4 NTC channels and update sliding dT/dt regression window
    NTCArraySummary sampleAll(uint32_t now_ms, const AlarmThresholds& limits);
    // Feed synthetic or external temperature sample (for testing/bench injection)
    void pushSample(uint8_t ch, float temp_c, uint32_t now_ms);

private:
    uint8_t pins_[NUM_NTC_CHANNELS]{};
    float   r_series_ohm_;
    float   v_ref_v_;
    float   sh_a_ = DEFAULT_SH_A;
    float   sh_b_ = DEFAULT_SH_B;
    float   sh_c_ = DEFAULT_SH_C;

    float    temp_hist_[NUM_NTC_CHANNELS][HISTORY_WINDOW]{};
    uint32_t time_hist_ms_[NUM_NTC_CHANNELS][HISTORY_WINDOW]{};
    uint8_t  hist_head_[NUM_NTC_CHANNELS]{};
    uint8_t  hist_count_[NUM_NTC_CHANNELS]{};

    float readPinVoltage(uint8_t pin) const;
};

}  // namespace cellguard
