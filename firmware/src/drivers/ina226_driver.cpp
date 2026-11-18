#include "drivers/ina226_driver.h"

#include <Arduino.h>
#include <Wire.h>
#include <math.h>

namespace cellguard {

volatile bool INA226Driver::isr_alert_latched_ = false;

void IRAM_ATTR INA226Driver::onAlertIsr() {
    isr_alert_latched_ = true;
}

INA226Driver::INA226Driver(uint8_t i2c_addr, int8_t alert_pin)
    : i2c_addr_(i2c_addr), alert_pin_(alert_pin) {}

float INA226Driver::computeCurrentLsb(float max_expected_current_a) {
    if (max_expected_current_a <= 0.0f) {
        return 0.001f;
    }
    // Datasheet eq. (1): Current_LSB = Max_Expected_Current / 2^15
    return max_expected_current_a / 32768.0f;
}

uint16_t INA226Driver::computeCalRegister(float r_shunt_ohm, float current_lsb_a) {
    if (r_shunt_ohm <= 0.0f || current_lsb_a <= 0.0f) {
        return 0;
    }
    // Datasheet eq. (2): CAL = trunc(0.00512 / (Current_LSB * R_shunt))
    const float raw_cal = 0.00512f / (current_lsb_a * r_shunt_ohm);
    if (raw_cal >= 32767.0f) {
        return 32767;
    }
    if (raw_cal < 1.0f) {
        return 1;
    }
    return static_cast<uint16_t>(floorf(raw_cal));
}

float INA226Driver::computePowerLsb(float current_lsb_a) {
    // Datasheet fixed multiplier: Power_LSB = 25 * Current_LSB
    return 25.0f * current_lsb_a;
}

uint16_t INA226Driver::buildConfigRegister(uint8_t avg_code, uint8_t vbus_ct, uint8_t vsh_ct, uint8_t mode) {
    return static_cast<uint16_t>(
        (0x4000u) |
        ((static_cast<uint16_t>(avg_code) & 0x07u) << 9) |
        ((static_cast<uint16_t>(vbus_ct)  & 0x07u) << 6) |
        ((static_cast<uint16_t>(vsh_ct)   & 0x07u) << 3) |
        (static_cast<uint16_t>(mode)      & 0x07u)
    );
}

bool INA226Driver::begin(float r_shunt_ohm, float max_expected_current_a) {
    if (alert_pin_ >= 0) {
        pinMode(alert_pin_, INPUT_PULLUP);
        attachInterrupt(digitalPinToInterrupt(alert_pin_), INA226Driver::onAlertIsr, FALLING);
    }

    uint16_t mfg_id = 0;
    uint16_t die_id = 0;
    if (!readRegister16(REG_MFG_ID, mfg_id) || !readRegister16(REG_DIE_ID, die_id)) {
        connected_ = false;
        return false;
    }
    if (mfg_id != MFG_ID_TI || (die_id & 0xFFF0u) != DIE_ID_INA226) {
        connected_ = false;
        return false;
    }

    connected_ = true;
    // AVG=2 (16 samples), VBUS_CT=4 (1.1 ms), VSH_CT=4 (1.1 ms), Mode=7 (continuous shunt & bus)
    const uint16_t cfg = buildConfigRegister(2, 4, 4, 7);
    if (!writeRegister16(REG_CONFIG, cfg)) {
        return false;
    }
    return reconfigureShunt(r_shunt_ohm, max_expected_current_a);
}

bool INA226Driver::reconfigureShunt(float r_shunt_ohm, float max_expected_current_a) {
    r_shunt_ohm_   = (r_shunt_ohm > 1e-6f) ? r_shunt_ohm : 0.001f;
    current_lsb_a_ = computeCurrentLsb(max_expected_current_a);
    cal_reg_       = computeCalRegister(r_shunt_ohm_, current_lsb_a_);
    // Recompute exact effective Current_LSB from truncated integer CAL register
    current_lsb_a_ = 0.00512f / (static_cast<float>(cal_reg_) * r_shunt_ohm_);
    power_lsb_w_   = computePowerLsb(current_lsb_a_);
    if (!connected_) {
        return true;
    }
    return writeRegister16(REG_CAL, cal_reg_);
}

bool INA226Driver::configureAlert(INA226AlertMode mode, float limit_value, bool latch_enable) {
    if (!connected_) {
        return false;
    }
    uint16_t alert_reg = 0;
    if (mode == INA226AlertMode::SHUNT_OVER_VOLT || mode == INA226AlertMode::SHUNT_UNDER_VOLT) {
        // limit_value in amperes -> convert to shunt voltage counts (2.5 uV/bit)
        const float v_shunt_v = limit_value * r_shunt_ohm_;
        const int32_t counts = static_cast<int32_t>(roundf(v_shunt_v / SHUNT_LSB_V));
        const int16_t clamped = static_cast<int16_t>(
            (counts > 32767) ? 32767 : ((counts < -32768) ? -32768 : counts)
        );
        alert_reg = static_cast<uint16_t>(clamped);
    } else if (mode == INA226AlertMode::BUS_OVER_VOLT || mode == INA226AlertMode::BUS_UNDER_VOLT) {
        // limit_value in volts -> 1.25 mV/bit
        const int32_t counts = static_cast<int32_t>(roundf(limit_value / BUS_LSB_V));
        alert_reg = static_cast<uint16_t>((counts > 32767) ? 32767 : ((counts < 0) ? 0 : counts));
    } else if (mode == INA226AlertMode::POWER_OVER_LIMIT) {
        const int32_t counts = static_cast<int32_t>(roundf(limit_value / power_lsb_w_));
        alert_reg = static_cast<uint16_t>((counts > 65535) ? 65535 : ((counts < 0) ? 0 : counts));
    }

    if (!writeRegister16(REG_ALERT_LIM, alert_reg)) {
        return false;
    }
    uint16_t mask_val = static_cast<uint16_t>(mode);
    if (latch_enable && mode != INA226AlertMode::ALERT_DISABLED) {
        mask_val |= 0x0001u;  // LEN=1, active-low APOL=0
    }
    return writeRegister16(REG_MASK_EN, mask_val);
}

void INA226Driver::setCalibration(float current_gain, float current_offset_a, float vbus_gain, float vbus_offset_v) {
    current_gain_     = current_gain;
    current_offset_a_ = current_offset_a;
    vbus_gain_        = vbus_gain;
    vbus_offset_v_    = vbus_offset_v;
}

bool INA226Driver::consumeAlertFlag() {
    if (isr_alert_latched_) {
        isr_alert_latched_ = false;
        return true;
    }
    return false;
}

INA226Sample INA226Driver::readSample() {
    INA226Sample s{};
    if (!connected_) {
        return s;
    }

    uint16_t raw_shunt = 0;
    uint16_t raw_bus   = 0;
    uint16_t raw_curr  = 0;
    uint16_t raw_pwr   = 0;
    uint16_t raw_mask  = 0;

    if (!readRegister16(REG_SHUNT_V, raw_shunt) ||
        !readRegister16(REG_BUS_V, raw_bus) ||
        !readRegister16(REG_CURRENT, raw_curr) ||
        !readRegister16(REG_POWER, raw_pwr)) {
        return s;
    }
    readRegister16(REG_MASK_EN, raw_mask);  // Clears AFF when latch enabled

    const int16_t signed_shunt = static_cast<int16_t>(raw_shunt);
    const int16_t signed_curr  = static_cast<int16_t>(raw_curr);

    s.shunt_voltage_mv = static_cast<float>(signed_shunt) * (SHUNT_LSB_V * 1000.0f);
    s.bus_voltage_v    = (static_cast<float>(raw_bus) * BUS_LSB_V) * vbus_gain_ + vbus_offset_v_;
    s.current_a        = (static_cast<float>(signed_curr) * current_lsb_a_) * current_gain_ + current_offset_a_;
    s.power_w          = s.bus_voltage_v * s.current_a;
    s.raw_mask_en      = raw_mask;
    s.alert_triggered  = ((raw_mask & 0x0010u) != 0) || consumeAlertFlag();
    s.valid            = true;
    return s;
}

bool INA226Driver::writeRegister16(uint8_t reg, uint16_t value) {
    Wire.beginTransmission(i2c_addr_);
    Wire.write(reg);
    Wire.write(static_cast<uint8_t>((value >> 8) & 0xFF));
    Wire.write(static_cast<uint8_t>(value & 0xFF));
    return Wire.endTransmission() == 0;
}

bool INA226Driver::readRegister16(uint8_t reg, uint16_t& out_value) {
    Wire.beginTransmission(i2c_addr_);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) {
        return false;
    }
    if (Wire.requestFrom(i2c_addr_, static_cast<uint8_t>(2)) != 2) {
        return false;
    }
    const uint16_t msb = Wire.read();
    const uint16_t lsb = Wire.read();
    out_value = (msb << 8) | lsb;
    return true;
}

}  // namespace cellguard
