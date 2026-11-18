// Wokwi Custom I2C Chip: TI INA226 (0x40) Telemetry Mock for CellGuard
// Implements 16-bit big-endian registers 0x00..0x07, MFG_ID (0xFE = 0x5449),
// DIE_ID (0xFF = 0x2260), and active-low ALERT output.

#include "wokwi-api.h"
#include <stdint.h>
#include <stdbool.h>

typedef struct {
  pin_t alert_pin;
  uint32_t bus_v_attr;
  uint32_t curr_a_attr;
  uint8_t reg_ptr;
  uint8_t rx_buf[3];
  uint8_t rx_len;
  uint16_t regs[8];
} chip_state_t;

static void update_measurements(chip_state_t *chip) {
  float bus_v = attr_read_float(chip->bus_v_attr);
  float curr_a = attr_read_float(chip->curr_a_attr);
  if (bus_v <= 0.0f) bus_v = 15.2f;  // Default 4S nominal

  // Shunt = 1.0 mOhm -> Vshunt = I * 0.001V; LSB = 2.5 uV
  int32_t shunt_raw = (int32_t)((curr_a * 0.001f) / 2.5e-6f);
  if (shunt_raw > 32767) shunt_raw = 32767;
  if (shunt_raw < -32768) shunt_raw = -32768;

  // Bus LSB = 1.25 mV
  uint16_t bus_raw = (uint16_t)(bus_v / 1.25e-3f);

  // Current register using Current_LSB = 60 / 32768
  float current_lsb = 60.0f / 32768.0f;
  int32_t curr_raw = (int32_t)(curr_a / current_lsb);
  if (curr_raw > 32767) curr_raw = 32767;
  if (curr_raw < -32768) curr_raw = -32768;

  chip->regs[0x01] = (uint16_t)(int16_t)shunt_raw;
  chip->regs[0x02] = bus_raw;
  chip->regs[0x04] = (uint16_t)(int16_t)curr_raw;
  chip->regs[0x03] = (uint16_t)((bus_v * (curr_a < 0 ? -curr_a : curr_a)) / (25.0f * current_lsb));

  // Trigger active-low ALERT if Shunt Over-Voltage limit exceeded
  uint16_t mask_en = chip->regs[0x06];
  uint16_t alert_lim = chip->regs[0x07];
  if ((mask_en & 0x8000) && ((int16_t)chip->regs[0x01] > (int16_t)alert_lim)) {
    pin_write(chip->alert_pin, LOW);
  } else {
    pin_write(chip->alert_pin, HIGH);
  }
}

static uint16_t read_register(chip_state_t *chip, uint8_t reg) {
  update_measurements(chip);
  if (reg < 8) return chip->regs[reg];
  if (reg == 0xFE) return 0x5449;  // TI Mfg ID
  if (reg == 0xFF) return 0x2260;  // INA226 Die ID
  return 0x0000;
}

static bool on_i2c_connect(void *user_data, uint32_t address, bool read) {
  chip_state_t *chip = (chip_state_t *)user_data;
  if (!read) {
    chip->rx_len = 0;
  }
  return address == 0x40;
}

static uint8_t on_i2c_read(void *user_data) {
  chip_state_t *chip = (chip_state_t *)user_data;
  uint16_t val = read_register(chip, chip->reg_ptr);
  uint8_t byte_idx = chip->rx_len & 0x01;
  chip->rx_len++;
  return byte_idx == 0 ? (uint8_t)(val >> 8) : (uint8_t)(val & 0xFF);
}

static bool on_i2c_write(void *user_data, uint8_t data) {
  chip_state_t *chip = (chip_state_t *)user_data;
  if (chip->rx_len == 0) {
    chip->reg_ptr = data;
    chip->rx_len = 1;
  } else if (chip->rx_len == 1) {
    chip->rx_buf[0] = data;
    chip->rx_len = 2;
  } else if (chip->rx_len == 2) {
    chip->rx_buf[1] = data;
    if (chip->reg_ptr < 8) {
      chip->regs[chip->reg_ptr] = ((uint16_t)chip->rx_buf[0] << 8) | chip->rx_buf[1];
    }
    chip->rx_len = 0;
  }
  return true;
}

void chip_init(void) {
  chip_state_t *chip = (chip_state_t *)malloc(sizeof(chip_state_t));
  chip->alert_pin = pin_init("ALERT", OUTPUT_HIGH);
  chip->bus_v_attr = attr_init_float("busVoltageV", 15.2f);
  chip->curr_a_attr = attr_init_float("packCurrentA", 10.0f);
  chip->reg_ptr = 0;
  chip->rx_len = 0;
  for (int i = 0; i < 8; i++) chip->regs[i] = 0;
  chip->regs[0x00] = 0x4127;

  const i2c_config_t i2c_cfg = {
    .address = 0x40,
    .scl = pin_init("SCL", INPUT),
    .sda = pin_init("SDA", INPUT),
    .connect = on_i2c_connect,
    .read = on_i2c_read,
    .write = on_i2c_write,
    .user_data = chip,
  };
  i2c_init(&i2c_cfg);
}
