# CellGuard PCB Assembly & Calibration Guide

## 1. Board Architecture Overview

The CellGuard hardware (`cellguard.kicad_pcb`, 2-layer FR4, 1.6 mm, 2 oz copper recommended) integrates four functional zones separated to prevent high-current ground bounce from corrupting millivolt Kelvin shunt measurements:

1. **High-Current Power Path (Top-Left Zone)**:
   - `J1` (`PACK_POS_IN`, XT60-M / Anderson / M4 lug) -> `R_SHUNT` (`1.0 mΩ` 4-terminal Kelvin shunt `CSS4J-4026R-1L00F` / `WSLP2726`) -> `J2` (`LOAD_POS_OUT`).
   - Wide `8.0 mm` copper polygons on `F.Cu` and `B.Cu` stitched with thermal/current via arrays (`Ø 0.4 mm` drill, `0.8 mm` pad) carry up to `60 A` continuous.
   - **Kelvin 4-Wire Sense Routing**: Inner sense traces (`SHUNT_SENSE_P`, `SHUNT_SENSE_N`) originate strictly inside the inner shunt sense tabs, routed symmetrically as a tight `0.25 mm` differential pair straight into the `10 Ω` RC anti-aliasing filter (`R10`, `R11`, `C4 = 100 nF`) at `U3 INA226AIDGSR`.
2. **Protected Sense-Tap Front End (Bottom-Left Zone)**:
   - `J3` (`JST-XH 7-pin` `B0..B6`) enters immediately into `F1..F6` (`0805` PPTC polyfuses, `100 mA` hold) and `D1..D6` (`SMAJ28A` TVS diodes to `GND`).
   - High-impedance `0.1%` 0805 dividers (`R_TOP1..6` and `R_BOT1..6 = 100 kΩ`) scale `B1..B6` to `0–2.3 V`, clamped to `3V3`/`AGND` via `BAT54S` dual Schottky arrays (`D8..D10`).
   - `U4` (`CD74HC4051` 8:1 MUX) selects `B1..B6`, `AGND` (`CH6`), and `2.048 V` precision reference `U6 LM4040AIM3-2.0` (`CH7`) into unity-gain buffer `U5 MCP6001` driving `GPIO36`.
3. **Thermal Sensor Array (Bottom-Right Zone)**:
   - `J6` (`JST-XH 8-pin` / 4x 2-pin pairs) connects four `10 kΩ @ 25°C` NTC probes (`NTC0..NTC3`) pulled up to `3V3` via `0.1%` `10.0 kΩ` resistors (`R20..R23`) with `100 nF` C0G filtering.
4. **ESP32-WROOM-32E Telemetry Core & Regulated 3.3V Supply (Right Zone)**:
   - `U1` (`ESP32-DevKitC-32E` / `ESP32-WROOM-32E`), `J4` (`USB-C` / UART bridge), `U2` (`AMS1117-3.3`), status/alarm LEDs (`D11`, `D12`), low-current piezo alert (`LS1` driven by `Q1 2N7002`), and `SW1` mute button.

---

## 2. SMT & Through-Hole Assembly Order

1. **Reflow / Fine-Pitch SMD First**:
   - Solder `U3` (`INA226AIDGSR`, VSSOP-10), `U4` (`CD74HC4051`, SOIC-16), `U5` (`MCP6001`, SOT-23-5), `U6` (`LM4040`, SOT-23), and `BAT54S` arrays.
   - Populate `0805` `0.1%` divider resistors, `100 nF` C0G/X7R capacitors, `F1..F7` PPTCs, and `D1..D7` TVS diodes.
2. **Power Shunt & Regulator**:
   - Solder `R_SHUNT` (`4-wire 1.0 mΩ`) with generous solder paste on the outer force pads; keep solder fillet clean on inner Kelvin tabs.
   - Solder `U2` (`AMS1117-3.3`) and `J4` USB-C receptacle.
3. **Through-Hole Headers & High-Current Terminals**:
   - Solder `J3` (`JST-XH 7-pin`), `J6` (`JST-XH 8-pin`), `U1` (`ESP32` module/headers), `SW1`, LEDs, and finally `J1`/`J2` high-current `XT60` / lug terminals using a high-thermal-capacity iron (`400 °C`).

---

## 3. Firmware Flash & Two-Point NVS Calibration

1. Flash firmware from `firmware/`:
   ```bash
   cd firmware
   pio run --target upload
   pio device monitor -b 115200
   ```
2. Complete Steps 1–4 of [`SAFETY-AND-TEST-PROCEDURE.md`](./SAFETY-AND-TEST-PROCEDURE.md) on a current-limited bench PSU.
3. Run the Python calibration utility or issue serial CLI commands directly:
   ```bash
   python calibration_cli.py --series-cells 4 --capacity-mah 5000 --shunt-mohm 1.0 --curr-meas1 0.02 --curr-ref1 0.00 --curr-meas2 19.85 --curr-ref2 20.00
   ```
4. Verify `SAVE` returns `{"ack":"NVS_SAVED"}` and power-cycle the ESP32 to confirm NVS calibration persistence via `SHOW`.
