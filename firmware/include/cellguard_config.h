#pragma once

#include <stdint.h>

/**
 * CellGuard Hardware Configuration & Non-Invasive Safety Guards
 *
 * CRITICAL SAFETY INVARIANT:
 * CellGuard is strictly a read-only telemetry and health analytics monitor.
 * It MUST always be operated in parallel with an external commercial BMS
 * and inline main fuse. No balancing, charging, or FET switching pins exist.
 */

#ifndef CELLGUARD_MONITOR_ONLY
#define CELLGUARD_MONITOR_ONLY 1
#endif
#define CELLGUARD_BALANCING_SUPPORTED 0
#define CELLGUARD_CHARGING_SUPPORTED 0
#define CELLGUARD_FET_SWITCHING_SUPPORTED 0

namespace cellguard {

// --- ESP32-WROOM-32E GPIO Pin Map (Matches KiCad 8 Schematic) ---
constexpr uint8_t PIN_I2C_SDA       = 21;
constexpr uint8_t PIN_I2C_SCL       = 22;
constexpr uint8_t PIN_INA_ALERT     = 16;  // Active-low open-drain alert from INA226

constexpr uint8_t PIN_CELL_MUX_ADC  = 36;  // ADC1_CH0 (input-only) via MCP6001 buffer
constexpr uint8_t PIN_MUX_S0        = 25;  // CD74HC4051 address bit 0
constexpr uint8_t PIN_MUX_S1        = 26;  // CD74HC4051 address bit 1
constexpr uint8_t PIN_MUX_S2        = 27;  // CD74HC4051 address bit 2

constexpr uint8_t PIN_NTC_0         = 39;  // ADC1_CH3 - Cell Group A core
constexpr uint8_t PIN_NTC_1         = 34;  // ADC1_CH6 - Cell Group B core
constexpr uint8_t PIN_NTC_2         = 35;  // ADC1_CH7 - External BMS / Busbar
constexpr uint8_t PIN_NTC_3         = 32;  // ADC1_CH4 - Shunt / Ambient reference

constexpr uint8_t PIN_LED_ALARM     = 17;  // Red hardware alarm indicator LED
constexpr uint8_t PIN_LED_STATUS    = 18;  // Green/Cyan heartbeat LED
constexpr uint8_t PIN_BUZZER_ALERT  = 19;  // Piezo alert buzzer (low-current signal only)
constexpr uint8_t PIN_CAL_BTN       = 4;   // Push-button for alarm mute / calibration ack

// --- System & Pack Constants ---
constexpr uint8_t MAX_SERIES_CELLS  = 6;
constexpr uint8_t NUM_NTC_CHANNELS  = 4;
constexpr float   ADC_VREF_DEFAULT_V = 3.300f;
constexpr float   MUX_VREF_PREC_V    = 2.048f;  // LM4040AIM3-2.0 precision reference on CH7

struct AlarmThresholds {
    float cell_ov_warn_v        = 4.21f;
    float cell_ov_crit_v        = 4.25f;
    float cell_uv_warn_v        = 3.00f;
    float cell_uv_crit_v        = 2.75f;
    float cell_delta_warn_mv    = 50.0f;
    float cell_delta_crit_mv    = 150.0f;
    float max_discharge_a       = 45.0f;
    float max_charge_a          = 15.0f;
    float temp_warn_c           = 50.0f;
    float temp_crit_c           = 60.0f;
    float dtdt_warn_c_per_min   = 2.0f;
    float dtdt_crit_c_per_min   = 5.0f;
    float rdc_ratio_warn        = 1.75f;
    float tap_mismatch_max_v    = 0.35f;
};

struct PackConfig {
    uint8_t series_cells          = 4;       // Configurable 1S..6S (default 4S 14.8V / 6S 22.2V)
    float   nominal_capacity_mah  = 5000.0f; // 21700 50E/M50T nominal pack capacity
    float   r_shunt_ohm           = 0.001f;  // 1.0 mOhm 4-wire Kelvin shunt
    float   max_expected_a        = 60.0f;   // Full-scale expected pack current
    float   r_dc_nominal_cell_mohm = 22.0f;  // New 21700 cell nominal DC-IR
    AlarmThresholds alarms{};
};

}  // namespace cellguard
