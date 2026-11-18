#pragma once

#include <stdint.h>
#include <stdbool.h>

/**
 * CellGuard Simulator-Independent Battery HAL Interface (C/C++)
 *
 * CRITICAL SAFETY INVARIANT:
 * CellGuard is strictly a NON-INVASIVE, READ-ONLY telemetry and health
 * analytics monitor operated alongside an external commercial BMS and inline
 * main fuse. This HAL exposes ZERO actuation, balancing, charging, or FET
 * switching methods.
 */

#ifndef CELLGUARD_MONITOR_ONLY
#define CELLGUARD_MONITOR_ONLY 1
#endif

#if CELLGUARD_MONITOR_ONLY != 1
#error "CELLGUARD_MONITOR_ONLY must remain 1. Actuation is prohibited."
#endif

namespace cellguard {
namespace sim_hal {

struct HalSafetyCapabilities {
    bool monitor_only            = true;
    bool balancing_supported     = false;
    bool charging_supported      = false;
    bool fet_switching_supported = false;
    bool external_bms_required   = true;
    bool inline_fuse_required    = true;
};

struct HalINA226Reading {
    float    bus_voltage_v    = 0.0f;
    float    shunt_voltage_mv = 0.0f;
    float    current_a        = 0.0f;
    float    power_w          = 0.0f;
    uint16_t mask_enable_reg  = 0;
    bool     alert_active     = false;
    bool     valid            = false;
};

struct HalNTCReading {
    float temp_c[4]           = {25.0f, 25.0f, 25.0f, 25.0f};
    float resistance_ohm[4]   = {10000.0f, 10000.0f, 10000.0f, 10000.0f};
    bool  sensor_fault[4]     = {false, false, false, false};
};

struct HalCellTapReading {
    uint8_t series_cells       = 4;
    float   tap_voltages_v[6]  = {0.0f};
    float   cell_voltages_v[6] = {0.0f};
    float   mux_gnd_offset_mv  = 0.0f;
    float   mux_vref_v         = 2.048f;
    bool    tap_fault          = false;
    bool    valid              = false;
};

struct HalAlarmOutputs {
    bool led_alarm_red   = false;  // GPIO17
    bool led_status_grn  = false;  // GPIO18
    bool buzzer_alert    = false;  // GPIO19 (low-current signal only)
    bool cal_btn_pressed = false;  // GPIO4  (active-low input)
};

class IBatteryHAL {
public:
    virtual ~IBatteryHAL() = default;

    virtual const char* backendName() const = 0;
    virtual HalSafetyCapabilities safetyCapabilities() const {
        return HalSafetyCapabilities{};
    }

    virtual bool init(uint8_t series_cells, float r_shunt_ohm, float max_expected_a) = 0;
    virtual HalINA226Reading readINA226() = 0;
    virtual HalNTCReading readNTCChannels() = 0;
    virtual HalCellTapReading readCellTapADC(uint8_t series_cells) = 0;
    virtual void writeAlarmOutputs(const HalAlarmOutputs& outputs) = 0;
};

}  // namespace sim_hal
}  // namespace cellguard
