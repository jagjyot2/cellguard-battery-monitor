/**
 * CellGuard Firmware Entry Point (ESP32-WROOM-32E)
 *
 * Non-Invasive 21700 Li-Ion Pack Telemetry & Health Analytics Instrument (1S-6S)
 * SAFETY: Strictly passive monitoring alongside an external commercial BMS + main fuse.
 *         Zero balancing, zero charging, zero high-current switching FET control.
 */

#include <Arduino.h>
#include <Wire.h>

#include "cellguard_config.h"
#include "drivers/ina226_driver.h"
#include "drivers/ntc_array.h"
#include "drivers/cell_tap_monitor.h"
#include "analytics/battery_analytics.h"
#include "calibration/cal_tool.h"

using namespace cellguard;

namespace {

constexpr uint8_t kNtcPins[NUM_NTC_CHANNELS] = {
    PIN_NTC_0, PIN_NTC_1, PIN_NTC_2, PIN_NTC_3
};

PackConfig       g_pack_cfg{};
INA226Driver     g_ina(INA226Driver::DEFAULT_ADDR, static_cast<int8_t>(PIN_INA_ALERT));
NTCArray         g_ntc(kNtcPins);
CellTapMonitor   g_taps(PIN_CELL_MUX_ADC, PIN_MUX_S0, PIN_MUX_S1, PIN_MUX_S2);
BatteryAnalytics g_analytics(g_pack_cfg);
CalTool          g_cal_tool;

INA226Sample     g_latest_ina{};
CellTapSnapshot  g_latest_taps{};
NTCArraySummary  g_latest_ntc{};

uint32_t g_last_fast_ms      = 0;
uint32_t g_last_telemetry_ms = 0;
bool     g_alarm_muted       = false;

void updateAlarmIndicators(uint32_t alarm_mask) {
    const bool critical = (alarm_mask & (
        ALARM_CELL_OV_CRIT | ALARM_CELL_UV_CRIT | ALARM_CELL_DELTA_CRIT |
        ALARM_OC_DISCHARGE | ALARM_OC_CHARGE | ALARM_TEMP_CRIT |
        ALARM_RUNAWAY_CRIT | ALARM_TAP_FAULT | ALARM_INA_HW_ALERT
    )) != 0;

    const bool any_alarm = (alarm_mask != ALARM_NONE);
    digitalWrite(PIN_LED_ALARM, any_alarm ? HIGH : LOW);
    digitalWrite(PIN_BUZZER_ALERT, (critical && !g_alarm_muted) ? HIGH : LOW);
}

void emitTelemetryJson(
    uint32_t now_ms,
    const INA226Sample& ina,
    const CellTapSnapshot& taps,
    const NTCArraySummary& ntc,
    const AnalyticsState& st) {

    Serial.printf(
        "{\"type\":\"telemetry\",\"ts_ms\":%lu,\"series_cells\":%u,"
        "\"bus_v\":%.4f,\"shunt_mv\":%.3f,\"current_a\":%.4f,\"power_w\":%.3f,"
        "\"soc_pct\":%.2f,\"soc_ocv_pct\":%.2f,\"soh_pct\":%.2f,"
        "\"mah_discharged\":%.2f,\"wh_discharged\":%.3f,"
        "\"r_dc_pack_ohm\":%.5f,\"r_dc_cell_mohm\":%.2f,"
        "\"cell_min_v\":%.4f,\"cell_max_v\":%.4f,\"cell_delta_mv\":%.1f,"
        "\"temp_max_c\":%.2f,\"dtdt_max_c_min\":%.2f,\"alarm_mask\":%lu,"
        "\"cells_v\":[",
        static_cast<unsigned long>(now_ms),
        taps.series_cells,
        ina.bus_voltage_v,
        ina.shunt_voltage_mv,
        ina.current_a,
        ina.power_w,
        st.soc_percent,
        st.soc_ocv_est_percent,
        st.soh_percent,
        st.mah_discharged,
        st.wh_discharged,
        st.r_dc_pack_ohm,
        st.r_dc_cell_mohm,
        taps.cell_min_v,
        taps.cell_max_v,
        taps.cell_delta_mv,
        ntc.max_temp_c,
        ntc.max_dtdt_c_per_min,
        static_cast<unsigned long>(st.alarm_mask)
    );

    for (uint8_t i = 0; i < taps.series_cells; ++i) {
        Serial.printf("%.4f%s", taps.cell_voltages_v[i], (i + 1 < taps.series_cells) ? "," : "");
    }
    Serial.print(F("],\"temps_c\":["));
    for (uint8_t i = 0; i < NUM_NTC_CHANNELS; ++i) {
        Serial.printf("%.2f%s", ntc.channels[i].temp_c, (i + 1 < NUM_NTC_CHANNELS) ? "," : "");
    }
    Serial.println(F("]}"));
}

}  // namespace

void setup() {
    Serial.begin(115200);
    delay(150);

    pinMode(PIN_LED_ALARM, OUTPUT);
    pinMode(PIN_LED_STATUS, OUTPUT);
    pinMode(PIN_BUZZER_ALERT, OUTPUT);
    pinMode(PIN_CAL_BTN, INPUT_PULLUP);
    digitalWrite(PIN_LED_ALARM, LOW);
    digitalWrite(PIN_LED_STATUS, HIGH);
    digitalWrite(PIN_BUZZER_ALERT, LOW);

    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
    Wire.setClock(400000);

    g_ntc.begin();
    g_taps.begin();

    const bool ina_ok = g_ina.begin(g_pack_cfg.r_shunt_ohm, g_pack_cfg.max_expected_a);
    g_cal_tool.begin(g_ina, g_taps, g_analytics, g_pack_cfg);

    if (ina_ok) {
        // Configure hardware ALERT latch on severe discharge overcurrent
        g_ina.configureAlert(INA226AlertMode::SHUNT_OVER_VOLT, g_pack_cfg.alarms.max_discharge_a, true);
    }

    g_latest_ina  = g_ina.readSample();
    g_latest_taps = g_taps.sampleTaps(g_latest_ina.valid ? g_latest_ina.bus_voltage_v : -1.0f,
                                      g_pack_cfg.alarms.tap_mismatch_max_v);
    g_analytics.resetSession(g_latest_taps.valid ? (g_latest_taps.pack_sum_v / g_pack_cfg.series_cells) : 3.80f);

    Serial.printf("{\"type\":\"boot\",\"fw\":\"%s\",\"monitor_only\":%d,\"ina226_ok\":%s}\n",
                  CELLGUARD_FW_VERSION,
                  CELLGUARD_MONITOR_ONLY,
                  ina_ok ? "true" : "false");

    g_last_fast_ms = millis();
    g_last_telemetry_ms = g_last_fast_ms;
}

void loop() {
    const uint32_t now_ms = millis();

    // Non-blocking calibration CLI
    g_cal_tool.pollSerialCli(g_latest_ina, g_latest_taps);

    if (digitalRead(PIN_CAL_BTN) == LOW) {
        g_alarm_muted = true;
    }

    // 50 ms fast INA226 acquisition loop for instantaneous load-step & overcurrent capture
    if (now_ms - g_last_fast_ms >= 50) {
        g_last_fast_ms = now_ms;
        if (g_ina.isConnected()) {
            g_latest_ina = g_ina.readSample();
        }
    }

    // 1000 ms full pack analytics & telemetry frame loop
    if (now_ms - g_last_telemetry_ms >= 1000) {
        const float dt_s = static_cast<float>(now_ms - g_last_telemetry_ms) / 1000.0f;
        g_last_telemetry_ms = now_ms;

        g_latest_ntc  = g_ntc.sampleAll(now_ms, g_pack_cfg.alarms);
        g_latest_taps = g_taps.sampleTaps(
            g_latest_ina.valid ? g_latest_ina.bus_voltage_v : -1.0f,
            g_pack_cfg.alarms.tap_mismatch_max_v
        );

        const float pack_v = g_latest_ina.valid ? g_latest_ina.bus_voltage_v : g_latest_taps.pack_sum_v;
        const float pack_i = g_latest_ina.valid ? g_latest_ina.current_a : 0.0f;
        const bool  hw_alt = g_latest_ina.valid && g_latest_ina.alert_triggered;

        const AnalyticsState& state = g_analytics.update(pack_v, pack_i, dt_s, g_latest_taps, g_latest_ntc, hw_alt);
        updateAlarmIndicators(state.alarm_mask);
        digitalWrite(PIN_LED_STATUS, !digitalRead(PIN_LED_STATUS));

        if (g_cal_tool.streamJsonEnabled()) {
            emitTelemetryJson(now_ms, g_latest_ina, g_latest_taps, g_latest_ntc, state);
        }
    }
}
