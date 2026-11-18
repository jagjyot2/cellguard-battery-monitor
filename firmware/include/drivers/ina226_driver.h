#pragma once

#include <stdint.h>
#ifdef ARDUINO
#include <Arduino.h>
#else
#ifndef IRAM_ATTR
#define IRAM_ATTR
#endif
#endif

namespace cellguard {

struct INA226Sample {
    float    bus_voltage_v    = 0.0f;
    float    shunt_voltage_mv = 0.0f;
    float    current_a        = 0.0f;
    float    power_w          = 0.0f;
    uint16_t raw_mask_en      = 0;
    bool     alert_triggered  = false;
    bool     valid            = false;
};

enum class INA226AlertMode : uint16_t {
    ALERT_DISABLED    = 0x0000,
    SHUNT_OVER_VOLT   = 0x8000,
    SHUNT_UNDER_VOLT  = 0x4000,
    BUS_OVER_VOLT     = 0x2000,
    BUS_UNDER_VOLT    = 0x1000,
    POWER_OVER_LIMIT  = 0x0800
};

class INA226Driver {
public:
    static constexpr uint8_t  DEFAULT_ADDR    = 0x40;
    static constexpr uint16_t MFG_ID_TI       = 0x5449;
    static constexpr uint16_t DIE_ID_INA226   = 0x2260;

    static constexpr uint8_t REG_CONFIG    = 0x00;
    static constexpr uint8_t REG_SHUNT_V   = 0x01;
    static constexpr uint8_t REG_BUS_V     = 0x02;
    static constexpr uint8_t REG_POWER     = 0x03;
    static constexpr uint8_t REG_CURRENT   = 0x04;
    static constexpr uint8_t REG_CAL       = 0x05;
    static constexpr uint8_t REG_MASK_EN   = 0x06;
    static constexpr uint8_t REG_ALERT_LIM = 0x07;
    static constexpr uint8_t REG_MFG_ID    = 0xFE;
    static constexpr uint8_t REG_DIE_ID    = 0xFF;

    static constexpr float SHUNT_LSB_V = 2.5e-6f;    // 2.5 uV/bit
    static constexpr float BUS_LSB_V   = 1.25e-3f;   // 1.25 mV/bit

    INA226Driver(uint8_t i2c_addr = DEFAULT_ADDR, int8_t alert_pin = -1);

    // Pure calibration math helpers (shared specification with Python suite)
    static float    computeCurrentLsb(float max_expected_current_a);
    static uint16_t computeCalRegister(float r_shunt_ohm, float current_lsb_a);
    static float    computePowerLsb(float current_lsb_a);
    static uint16_t buildConfigRegister(uint8_t avg_code = 2, uint8_t vbus_ct = 4, uint8_t vsh_ct = 4, uint8_t mode = 7);

    bool begin(float r_shunt_ohm, float max_expected_current_a);
    bool reconfigureShunt(float r_shunt_ohm, float max_expected_current_a);
    bool configureAlert(INA226AlertMode mode, float limit_value, bool latch_enable = true);

    void setCalibration(float current_gain, float current_offset_a, float vbus_gain, float vbus_offset_v);
    INA226Sample readSample();

    bool     isConnected() const { return connected_; }
    float    currentLsb() const { return current_lsb_a_; }
    uint16_t calRegister() const { return cal_reg_; }
    bool     consumeAlertFlag();

    static void IRAM_ATTR onAlertIsr();

private:
    uint8_t  i2c_addr_;
    int8_t   alert_pin_;
    bool     connected_       = false;
    float    r_shunt_ohm_     = 0.001f;
    float    current_lsb_a_   = 0.002f;
    float    power_lsb_w_     = 0.050f;
    uint16_t cal_reg_         = 2560;

    float current_gain_       = 1.0f;
    float current_offset_a_   = 0.0f;
    float vbus_gain_          = 1.0f;
    float vbus_offset_v_      = 0.0f;

    static volatile bool isr_alert_latched_;

    bool writeRegister16(uint8_t reg, uint16_t value);
    bool readRegister16(uint8_t reg, uint16_t& out_value);
};

}  // namespace cellguard
