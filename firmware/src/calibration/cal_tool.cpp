#include "calibration/cal_tool.h"

#include <Arduino.h>
#include <Preferences.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace cellguard {

namespace {
constexpr char kNvsNamespace[] = "cellguard";
constexpr char kNvsKeyBlob[]   = "cal_v1";
}  // namespace

bool CalTool::computeTwoPoint(float meas1, float ref1, float meas2, float ref2, float& out_gain, float& out_offset) {
    const float denom = meas2 - meas1;
    if (fabsf(denom) < 1e-4f) {
        return false;
    }
    out_gain   = (ref2 - ref1) / denom;
    out_offset = ref1 - out_gain * meas1;
    return true;
}

uint16_t CalTool::computeCrc16(const uint8_t* data, uint32_t len) {
    uint16_t crc = 0xFFFFu;
    for (uint32_t i = 0; i < len; ++i) {
        crc ^= static_cast<uint16_t>(data[i]) << 8;
        for (uint8_t b = 0; b < 8; ++b) {
            if (crc & 0x8000u) {
                crc = static_cast<uint16_t>((crc << 1) ^ 0x1021u);
            } else {
                crc = static_cast<uint16_t>(crc << 1);
            }
        }
    }
    return crc;
}

void CalTool::begin(INA226Driver& ina, CellTapMonitor& taps, BatteryAnalytics& analytics, PackConfig& cfg) {
    ina_       = &ina;
    taps_      = &taps;
    analytics_ = &analytics;
    cfg_       = &cfg;

    if (!loadFromNvs()) {
        resetDefaults();
    }
    applyProfile();
}

void CalTool::resetDefaults() {
    profile_ = CalibrationProfile{};
    if (cfg_ != nullptr) {
        profile_.series_cells    = cfg_->series_cells;
        profile_.nominal_cap_mah = cfg_->nominal_capacity_mah;
        profile_.r_shunt_ohm     = cfg_->r_shunt_ohm;
        profile_.r_dc_nom_mohm   = cfg_->r_dc_nominal_cell_mohm;
    }
}

void CalTool::applyProfile() {
    if (cfg_ != nullptr) {
        cfg_->series_cells           = profile_.series_cells;
        cfg_->nominal_capacity_mah   = profile_.nominal_cap_mah;
        cfg_->r_shunt_ohm            = profile_.r_shunt_ohm;
        cfg_->r_dc_nominal_cell_mohm = profile_.r_dc_nom_mohm;
    }
    if (ina_ != nullptr) {
        ina_->reconfigureShunt(profile_.r_shunt_ohm, cfg_ ? cfg_->max_expected_a : 60.0f);
        ina_->setCalibration(profile_.current_gain, profile_.current_offset_a, profile_.vbus_gain, profile_.vbus_offset_v);
    }
    if (taps_ != nullptr) {
        taps_->setSeriesCells(profile_.series_cells);
        for (uint8_t i = 0; i < MAX_SERIES_CELLS; ++i) {
            taps_->setChannelCalibration(i, profile_.tap_gain[i], profile_.tap_offset_v[i]);
        }
    }
    if (analytics_ != nullptr && cfg_ != nullptr) {
        analytics_->updateConfig(*cfg_);
    }
}

bool CalTool::loadFromNvs() {
    Preferences prefs;
    if (!prefs.begin(kNvsNamespace, true)) {
        return false;
    }
    CalibrationProfile loaded{};
    const size_t n = prefs.getBytes(kNvsKeyBlob, &loaded, sizeof(CalibrationProfile));
    prefs.end();

    if (n != sizeof(CalibrationProfile) || loaded.magic != 0x43475631u) {
        return false;
    }
    const uint16_t expected_crc = computeCrc16(
        reinterpret_cast<const uint8_t*>(&loaded),
        sizeof(CalibrationProfile) - sizeof(uint16_t)
    );
    if (loaded.crc16 != expected_crc) {
        return false;
    }
    if (loaded.series_cells < 1 || loaded.series_cells > MAX_SERIES_CELLS) {
        return false;
    }
    profile_ = loaded;
    return true;
}

bool CalTool::saveToNvs() {
    profile_.magic = 0x43475631u;
    profile_.crc16 = computeCrc16(
        reinterpret_cast<const uint8_t*>(&profile_),
        sizeof(CalibrationProfile) - sizeof(uint16_t)
    );
    Preferences prefs;
    if (!prefs.begin(kNvsNamespace, false)) {
        return false;
    }
    const size_t written = prefs.putBytes(kNvsKeyBlob, &profile_, sizeof(CalibrationProfile));
    prefs.end();
    return written == sizeof(CalibrationProfile);
}

void CalTool::printHelp() const {
    Serial.println(F("\n=== CellGuard NVS Calibration CLI (Monitor-Only Instrument) ==="));
    Serial.println(F("  SHOW                          - Print active NVS calibration & pack profile"));
    Serial.println(F("  SET_PACK <cells> <mah> <mohm> - Configure 1-6S cells, capacity mAh, shunt mOhm"));
    Serial.println(F("  CAL_CURR_PT1 <ref_A>          - Capture point 1 current against reference DMM"));
    Serial.println(F("  CAL_CURR_PT2 <ref_A>          - Capture point 2 current & apply 2-point fit"));
    Serial.println(F("  CAL_VBUS_PT1 <ref_V>          - Capture point 1 bus voltage against DMM"));
    Serial.println(F("  CAL_VBUS_PT2 <ref_V>          - Capture point 2 bus voltage & apply 2-point fit"));
    Serial.println(F("  SET_TAP_CAL <ch> <gain> <off> - Set tap ch (1-6) linear gain & offset (V)"));
    Serial.println(F("  SAVE                          - Commit calibration profile to ESP32 NVS"));
    Serial.println(F("  RESET_CAL                     - Restore factory defaults"));
    Serial.println(F("  JSON_ON / JSON_OFF            - Toggle 1 Hz JSON telemetry stream\n"));
}

void CalTool::printProfile() const {
    Serial.printf(
        "{\"type\":\"cal_profile\",\"series_cells\":%u,\"nominal_mah\":%.1f,"
        "\"r_shunt_mohm\":%.4f,\"current_gain\":%.6f,\"current_offset_a\":%.6f,"
        "\"vbus_gain\":%.6f,\"vbus_offset_v\":%.6f,\"tap_gain\":[%.5f,%.5f,%.5f,%.5f,%.5f,%.5f],"
        "\"tap_offset_v\":[%.5f,%.5f,%.5f,%.5f,%.5f,%.5f]}\n",
        profile_.series_cells,
        profile_.nominal_cap_mah,
        profile_.r_shunt_ohm * 1000.0f,
        profile_.current_gain,
        profile_.current_offset_a,
        profile_.vbus_gain,
        profile_.vbus_offset_v,
        profile_.tap_gain[0], profile_.tap_gain[1], profile_.tap_gain[2],
        profile_.tap_gain[3], profile_.tap_gain[4], profile_.tap_gain[5],
        profile_.tap_offset_v[0], profile_.tap_offset_v[1], profile_.tap_offset_v[2],
        profile_.tap_offset_v[3], profile_.tap_offset_v[4], profile_.tap_offset_v[5]
    );
}

void CalTool::pollSerialCli(const INA226Sample& latest_ina, const CellTapSnapshot& latest_taps) {
    while (Serial.available() > 0) {
        const char c = static_cast<char>(Serial.read());
        if (c == '\r' || c == '\n') {
            if (rx_len_ > 0) {
                rx_buf_[rx_len_] = '\0';
                handleCommand(rx_buf_, latest_ina, latest_taps);
                rx_len_ = 0;
            }
        } else if (rx_len_ < sizeof(rx_buf_) - 1) {
            rx_buf_[rx_len_++] = c;
        }
    }
}

void CalTool::handleCommand(const char* line, const INA226Sample& latest_ina, const CellTapSnapshot& latest_taps) {
    (void)latest_taps;
    char cmd[32]{};
    float a1 = 0.0f, a2 = 0.0f, a3 = 0.0f;
    const int parsed = sscanf(line, "%31s %f %f %f", cmd, &a1, &a2, &a3);
    if (parsed < 1) return;

    if (strcmp(cmd, "HELP") == 0) {
        printHelp();
    } else if (strcmp(cmd, "SHOW") == 0) {
        printProfile();
    } else if (strcmp(cmd, "JSON_ON") == 0) {
        json_stream_enabled_ = true;
        Serial.println(F("{\"ack\":\"JSON_ON\"}"));
    } else if (strcmp(cmd, "JSON_OFF") == 0) {
        json_stream_enabled_ = false;
        Serial.println(F("{\"ack\":\"JSON_OFF\"}"));
    } else if (strcmp(cmd, "SET_PACK") == 0 && parsed == 4) {
        const int cells = static_cast<int>(roundf(a1));
        if (cells < 1 || cells > MAX_SERIES_CELLS || a2 < 100.0f || a3 <= 0.05f) {
            Serial.println(F("{\"err\":\"invalid SET_PACK args\"}"));
            return;
        }
        profile_.series_cells    = static_cast<uint8_t>(cells);
        profile_.nominal_cap_mah = a2;
        profile_.r_shunt_ohm     = a3 / 1000.0f;
        applyProfile();
        printProfile();
    } else if (strcmp(cmd, "CAL_CURR_PT1") == 0 && parsed >= 2) {
        // Uncalibrate back to raw reading before capturing two-point reference
        const float raw_i = (latest_ina.current_a - profile_.current_offset_a) / profile_.current_gain;
        curr_meas1_ = raw_i;
        curr_ref1_  = a1;
        has_curr_pt1_ = true;
        Serial.printf("{\"ack\":\"CAL_CURR_PT1\",\"meas_raw_a\":%.4f,\"ref_a\":%.4f}\n", curr_meas1_, curr_ref1_);
    } else if (strcmp(cmd, "CAL_CURR_PT2") == 0 && parsed >= 2) {
        if (!has_curr_pt1_) {
            Serial.println(F("{\"err\":\"Run CAL_CURR_PT1 first\"}"));
            return;
        }
        const float raw_i2 = (latest_ina.current_a - profile_.current_offset_a) / profile_.current_gain;
        float g = 1.0f, off = 0.0f;
        if (!computeTwoPoint(curr_meas1_, curr_ref1_, raw_i2, a1, g, off)) {
            Serial.println(F("{\"err\":\"Degenerate current calibration span\"}"));
            return;
        }
        profile_.current_gain     = g;
        profile_.current_offset_a = off;
        has_curr_pt1_ = false;
        applyProfile();
        printProfile();
    } else if (strcmp(cmd, "CAL_VBUS_PT1") == 0 && parsed >= 2) {
        const float raw_v = (latest_ina.bus_voltage_v - profile_.vbus_offset_v) / profile_.vbus_gain;
        vbus_meas1_ = raw_v;
        vbus_ref1_  = a1;
        has_vbus_pt1_ = true;
        Serial.printf("{\"ack\":\"CAL_VBUS_PT1\",\"meas_raw_v\":%.4f,\"ref_v\":%.4f}\n", vbus_meas1_, vbus_ref1_);
    } else if (strcmp(cmd, "CAL_VBUS_PT2") == 0 && parsed >= 2) {
        if (!has_vbus_pt1_) {
            Serial.println(F("{\"err\":\"Run CAL_VBUS_PT1 first\"}"));
            return;
        }
        const float raw_v2 = (latest_ina.bus_voltage_v - profile_.vbus_offset_v) / profile_.vbus_gain;
        float g = 1.0f, off = 0.0f;
        if (!computeTwoPoint(vbus_meas1_, vbus_ref1_, raw_v2, a1, g, off)) {
            Serial.println(F("{\"err\":\"Degenerate bus voltage span\"}"));
            return;
        }
        profile_.vbus_gain     = g;
        profile_.vbus_offset_v = off;
        has_vbus_pt1_ = false;
        applyProfile();
        printProfile();
    } else if (strcmp(cmd, "SET_TAP_CAL") == 0 && parsed == 4) {
        const int ch = static_cast<int>(roundf(a1)) - 1;
        if (ch < 0 || ch >= MAX_SERIES_CELLS || a2 <= 0.1f) {
            Serial.println(F("{\"err\":\"SET_TAP_CAL requires ch 1-6 and valid gain\"}"));
            return;
        }
        profile_.tap_gain[ch]     = a2;
        profile_.tap_offset_v[ch] = a3;
        applyProfile();
        printProfile();
    } else if (strcmp(cmd, "SAVE") == 0) {
        if (saveToNvs()) {
            Serial.println(F("{\"ack\":\"NVS_SAVED\"}"));
        } else {
            Serial.println(F("{\"err\":\"NVS_SAVE_FAILED\"}"));
        }
    } else if (strcmp(cmd, "RESET_CAL") == 0) {
        resetDefaults();
        applyProfile();
        Serial.println(F("{\"ack\":\"DEFAULTS_RESTORED\"}"));
    } else {
        Serial.println(F("{\"err\":\"Unknown command. Send HELP\"}"));
    }
}

}  // namespace cellguard
