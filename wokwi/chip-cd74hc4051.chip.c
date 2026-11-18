// Wokwi Custom Chip Stub: CD74HC4051 8:1 Analog Multiplexer for CellGuard
// Routes S0/S1/S2 address lines (GPIO25/26/27) to COM_OUT (GPIO36) with
// CH6=0V (AGND) and CH7=2.048V (LM4040 precision reference).

#include "wokwi-api.h"
#include <stdint.h>

typedef struct {
  pin_t s0;
  pin_t s1;
  pin_t s2;
  pin_t com_out;
  pin_t ch[6];
} mux_state_t;

static void update_mux(void *user_data, pin_t pin, uint32_t value) {
  (void)pin;
  (void)value;
  mux_state_t *mux = (mux_state_t *)user_data;
  uint8_t sel = (pin_read(mux->s0) ? 1 : 0) |
                (pin_read(mux->s1) ? 2 : 0) |
                (pin_read(mux->s2) ? 4 : 0);
  if (sel < 6) {
    pin_dac_write(mux->com_out, pin_adc_read(mux->ch[sel]));
  } else if (sel == 6) {
    pin_dac_write(mux->com_out, 0.0f);
  } else {
    pin_dac_write(mux->com_out, 2.048f);
  }
}

void chip_init(void) {
  mux_state_t *mux = (mux_state_t *)malloc(sizeof(mux_state_t));
  mux->s0 = pin_init("S0", INPUT);
  mux->s1 = pin_init("S1", INPUT);
  mux->s2 = pin_init("S2", INPUT);
  mux->com_out = pin_init("COM_OUT", ANALOG);
  mux->ch[0] = pin_init("CH0", ANALOG);
  mux->ch[1] = pin_init("CH1", ANALOG);
  mux->ch[2] = pin_init("CH2", ANALOG);
  mux->ch[3] = pin_init("CH3", ANALOG);
  mux->ch[4] = pin_init("CH4", ANALOG);
  mux->ch[5] = pin_init("CH5", ANALOG);

  const pin_watch_config_t watch_cfg = {
    .edge = BOTH,
    .pin_change = update_mux,
    .user_data = mux,
  };
  pin_watch(mux->s0, &watch_cfg);
  pin_watch(mux->s1, &watch_cfg);
  pin_watch(mux->s2, &watch_cfg);
}
