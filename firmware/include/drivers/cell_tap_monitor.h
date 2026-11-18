#pragma once

#include <stdint.h>
#include "cellguard_config.h"

namespace cellguard {

struct CellTapSnapshot {
    uint8_t series_cells               = 4;
    float   tap_voltages_v[MAX_SERIES_CELLS]{};
    float   cell_voltages_v[MAX_SERIES_CELLS]{};
    float   pack_sum_v                 = 0.0f;
    float   cell_min_v                 = 0.0f;
    float   cell_max_v                 = 0.0f;
    float   cell_delta_mv              = 0.0f;
    float   mux_gnd_offset_mv          = 0.0f;
    float   mux_vref_measured_v        = MUX_VREF_PREC_V;
    bool    tap_fault                  = false;
    bool    valid                      = false;
};

class CellTapMonitor {
public:
    // Nominal high-impedance divider ratios (R_top + 100k) / 100k for B1..B6
    static constexpr float DEFAULT_DIVIDER_RATIOS[MAX_SERIES_CELLS] = {
        2.00f,  // B1: 100k / 100k (4.20V -> 2.100V)
        4.00f,  // B2: 300k / 100k (8.40V -> 2.100V)
        5.99f,  // B3: 499k / 100k (12.6V -> 2.104V)
        7.80f,  // B4: 680k / 100k (16.8V -> 2.154V)
        9.20f,  // B5: 820k / 100k (21.0V -> 2.283V)
        11.00f  // B6: 1.0M / 100k (25.2V -> 2.291V)
    };

    static constexpr uint8_t MUX_CH_GND  = 6;
    static constexpr uint8_t MUX_CH_VREF = 7;

    CellTapMonitor(uint8_t adc_pin, uint8_t s0_pin, uint8_t s1_pin, uint8_t s2_pin);

    void begin();
    void setSeriesCells(uint8_t series_cells);
    void setChannelCalibration(uint8_t ch, float gain, float offset_v);
    void getChannelCalibration(uint8_t ch, float& gain, float& offset_v) const;

    CellTapSnapshot sampleTaps(float ina_bus_voltage_v = -1.0f, float mismatch_thresh_v = 0.35f);

    // Pure math helper for computing differential cell metrics from calibrated tap array
    static void computeCellDeltas(CellTapSnapshot& snap, float ina_bus_voltage_v, float mismatch_thresh_v);

private:
    uint8_t adc_pin_;
    uint8_t s0_pin_;
    uint8_t s1_pin_;
    uint8_t s2_pin_;
    uint8_t series_cells_ = 4;

    float cal_gain_[MAX_SERIES_CELLS]{1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f};
    float cal_offset_v_[MAX_SERIES_CELLS]{0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f};

    void  selectMuxChannel(uint8_t ch) const;
    float readMuxMilliVoltsAvg(uint8_t ch, uint8_t num_samples = 32) const;
};

}  // namespace cellguard
