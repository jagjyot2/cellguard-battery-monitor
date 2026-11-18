#include "drivers/cell_tap_monitor.h"

#include <Arduino.h>
#include <math.h>

namespace cellguard {

constexpr float CellTapMonitor::DEFAULT_DIVIDER_RATIOS[MAX_SERIES_CELLS];

CellTapMonitor::CellTapMonitor(uint8_t adc_pin, uint8_t s0_pin, uint8_t s1_pin, uint8_t s2_pin)
    : adc_pin_(adc_pin), s0_pin_(s0_pin), s1_pin_(s1_pin), s2_pin_(s2_pin) {}

void CellTapMonitor::begin() {
    pinMode(s0_pin_, OUTPUT);
    pinMode(s1_pin_, OUTPUT);
    pinMode(s2_pin_, OUTPUT);
    pinMode(adc_pin_, INPUT);
    analogReadResolution(12);
    analogSetPinAttenuation(adc_pin_, ADC_11db);
    selectMuxChannel(MUX_CH_GND);
}

void CellTapMonitor::setSeriesCells(uint8_t series_cells) {
    if (series_cells < 1) series_cells = 1;
    if (series_cells > MAX_SERIES_CELLS) series_cells = MAX_SERIES_CELLS;
    series_cells_ = series_cells;
}

void CellTapMonitor::setChannelCalibration(uint8_t ch, float gain, float offset_v) {
    if (ch < MAX_SERIES_CELLS) {
        cal_gain_[ch] = gain;
        cal_offset_v_[ch] = offset_v;
    }
}

void CellTapMonitor::getChannelCalibration(uint8_t ch, float& gain, float& offset_v) const {
    if (ch < MAX_SERIES_CELLS) {
        gain = cal_gain_[ch];
        offset_v = cal_offset_v_[ch];
    } else {
        gain = 1.0f;
        offset_v = 0.0f;
    }
}

void CellTapMonitor::selectMuxChannel(uint8_t ch) const {
    digitalWrite(s0_pin_, (ch & 0x01u) ? HIGH : LOW);
    digitalWrite(s1_pin_, (ch & 0x02u) ? HIGH : LOW);
    digitalWrite(s2_pin_, (ch & 0x04u) ? HIGH : LOW);
    delayMicroseconds(250);  // Allow MUX switch + 100nF RC filter settling
}

float CellTapMonitor::readMuxMilliVoltsAvg(uint8_t ch, uint8_t num_samples) const {
    selectMuxChannel(ch);
    uint32_t mv_sum = 0;
    for (uint8_t i = 0; i < num_samples; ++i) {
        mv_sum += analogReadMilliVolts(adc_pin_);
    }
    return static_cast<float>(mv_sum) / static_cast<float>(num_samples);
}

void CellTapMonitor::computeCellDeltas(CellTapSnapshot& snap, float ina_bus_voltage_v, float mismatch_thresh_v) {
    float min_v = 100.0f;
    float max_v = -100.0f;
    bool fault = false;

    for (uint8_t i = 0; i < snap.series_cells; ++i) {
        const float v_prev = (i == 0) ? 0.0f : snap.tap_voltages_v[i - 1];
        const float v_cell = snap.tap_voltages_v[i] - v_prev;
        snap.cell_voltages_v[i] = v_cell;
        if (v_cell < min_v) min_v = v_cell;
        if (v_cell > max_v) max_v = v_cell;
        if (v_cell < 0.50f || v_cell > 4.60f) {
            fault = true;
        }
    }
    snap.pack_sum_v = (snap.series_cells > 0) ? snap.tap_voltages_v[snap.series_cells - 1] : 0.0f;
    snap.cell_min_v = (snap.series_cells > 0) ? min_v : 0.0f;
    snap.cell_max_v = (snap.series_cells > 0) ? max_v : 0.0f;
    snap.cell_delta_mv = (snap.cell_max_v - snap.cell_min_v) * 1000.0f;

    if (ina_bus_voltage_v > 0.5f && fabsf(snap.pack_sum_v - ina_bus_voltage_v) > mismatch_thresh_v) {
        fault = true;
    }
    snap.tap_fault = fault;
    snap.valid = true;
}

CellTapSnapshot CellTapMonitor::sampleTaps(float ina_bus_voltage_v, float mismatch_thresh_v) {
    CellTapSnapshot snap{};
    snap.series_cells = series_cells_;

    // Read internal zero-offset and 2.048V precision reference channels on MUX CH6/CH7
    const float gnd_mv  = readMuxMilliVoltsAvg(MUX_CH_GND, 16);
    const float vref_mv = readMuxMilliVoltsAvg(MUX_CH_VREF, 16);
    snap.mux_gnd_offset_mv = gnd_mv;
    snap.mux_vref_measured_v = vref_mv / 1000.0f;

    float ref_scale = 1.0f;
    if (vref_mv > 1800.0f && vref_mv < 2300.0f && (vref_mv - gnd_mv) > 100.0f) {
        ref_scale = (MUX_VREF_PREC_V * 1000.0f) / (vref_mv - gnd_mv);
    }

    for (uint8_t i = 0; i < series_cells_; ++i) {
        const float raw_mv = readMuxMilliVoltsAvg(i, 32);
        const float corrected_adc_v = ((raw_mv - gnd_mv) / 1000.0f) * ref_scale;
        const float v_tap_uncal = corrected_adc_v * DEFAULT_DIVIDER_RATIOS[i];
        snap.tap_voltages_v[i] = v_tap_uncal * cal_gain_[i] + cal_offset_v_[i];
    }

    computeCellDeltas(snap, ina_bus_voltage_v, mismatch_thresh_v);
    return snap;
}

}  // namespace cellguard
