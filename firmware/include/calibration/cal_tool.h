#pragma once

#include <stdint.h>
#include "cellguard_config.h"
#include "drivers/ina226_driver.h"
#include "drivers/cell_tap_monitor.h"
#include "analytics/battery_analytics.h"

namespace cellguard {

struct CalibrationProfile {
    uint32_t magic           = 0x43475631;  // "CGV1"
    uint8_t  series_cells    = 4;
    float    nominal_cap_mah = 5000.0f;
    float    r_shunt_ohm     = 0.001f;
    float    r_dc_nom_mohm   = 22.0f;
    float    current_gain    = 1.0f;
    float    current_offset_a = 0.0f;
    float    vbus_gain       = 1.0f;
    float    vbus_offset_v   = 0.0f;
    float    tap_gain[MAX_SERIES_CELLS]{1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f};
    float    tap_offset_v[MAX_SERIES_CELLS]{0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f};
    uint16_t crc16           = 0;
};

class CalTool {
public:
    static bool computeTwoPoint(float meas1, float ref1, float meas2, float ref2, float& out_gain, float& out_offset);
    static uint16_t computeCrc16(const uint8_t* data, uint32_t len);

    void begin(INA226Driver& ina, CellTapMonitor& taps, BatteryAnalytics& analytics, PackConfig& cfg);
    bool loadFromNvs();
    bool saveToNvs();
    void resetDefaults();
    void applyProfile();

    // Processes incoming USB-UART calibration commands without blocking telemetry
    void pollSerialCli(const INA226Sample& latest_ina, const CellTapSnapshot& latest_taps);
    void printHelp() const;
    void printProfile() const;

    bool streamJsonEnabled() const { return json_stream_enabled_; }
    const CalibrationProfile& profile() const { return profile_; }

private:
    CalibrationProfile profile_{};
    INA226Driver*      ina_       = nullptr;
    CellTapMonitor*    taps_      = nullptr;
    BatteryAnalytics*  analytics_ = nullptr;
    PackConfig*        cfg_       = nullptr;

    bool   json_stream_enabled_ = true;
    char   rx_buf_[160]{};
    uint8_t rx_len_ = 0;

    // Two-point interactive buffer for live bench measurement points
    bool  has_curr_pt1_ = false;
    float curr_meas1_ = 0.0f, curr_ref1_ = 0.0f;
    bool  has_vbus_pt1_ = false;
    float vbus_meas1_ = 0.0f, vbus_ref1_ = 0.0f;

    void handleCommand(const char* line, const INA226Sample& latest_ina, const CellTapSnapshot& latest_taps);
};

}  // namespace cellguard
