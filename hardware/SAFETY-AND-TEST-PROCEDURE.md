# CellGuard Hardware Safety & Bench Test Procedure

> **CRITICAL SAFETY CLASSIFICATION**  
> **CellGuard is strictly a NON-INVASIVE, READ-ONLY battery telemetry and health analytics monitor.**  
> CellGuard **MUST ONLY** be deployed **in parallel with an external commercial BMS (Battery Management System) and an inline main high-rupture-capacity fuse** sized for the 21700 pack.  
> CellGuard implements **NO** cell balancing, **NO** battery charging control, and **NO** high-current MOSFET disconnection or load switching.

---

## 1. Non-Negotiable Safety Architecture

1. **External Commercial BMS Mandatory**:
   - Pack over-charge cutoff, over-discharge cutoff, short-circuit protection, and passive/active cell balancing **must be performed exclusively by an external certified BMS** wired between the 21700 cells and the pack terminals.
   - CellGuard monitors **downstream** of the pack's main fuse on the positive bus (`J1 PACK_POS_IN` -> `1.0 mΩ Kelvin Shunt R_SHUNT` -> `J2 LOAD_POS_OUT`) and taps the commercial BMS balance harness non-invasively via high-impedance protected sense leads (`J3`).
2. **Inline Main Fuse Mandatory**:
   - Install an automotive/marine DC fuse (`F_MAIN`, e.g., **40 A–60 A MIDI/ANL/Blade** rated ≥ 32 V DC for 4S/6S packs) on `PACK+` directly at the battery positive terminal before `J1 PACK_POS_IN`.
3. **Sense-Tap Input Protection (`J3` B1–B6 & VBUS)**:
   - Every cell group tap (`B1` through `B6`) and the `VBUS` sense line passes through:
     - **Resettable PPTC Polyfuse (`F1..F7`)**: `100 mA` hold / `200 mA` trip, `60 V` DC rated (Bourns `MF-PSMF010X-2` / Littelfuse `0805L010YR`) located immediately adjacent to connector `J3`.
     - **TVS Clamping Diode (`D1..D7`)**: `SMBJ28A` / `SMAJ28A` (`28 V` standoff, clamping inductive load-dump spikes cleanly below the 36 V INA226 & resistor ratings).
     - **High-Impedance Precision Dividers (`0.1%`, ≥ 200 kΩ to 1.1 MΩ)**: Limits steady-state tap bleed current to `< 25 µA` per tap and caps worst-case downstream fault current to sub-milliamp levels.
     - **ADC Rail Clamp (`D8..D14`, `BAT54S`)**: Dual-Schottky clamp to `3V3` and `AGND` protecting `CD74HC4051` MUX inputs and ESP32 ADC1 pins against any positive or negative excursion.
4. **Power Domain Isolation**:
   - Logic power (`5 V` USB-C `J4` or isolated DC-DC `5 V` header `J5` -> `U2 AMS1117-3.3`) is completely decoupled from individual cell taps so CellGuard **never creates an unbalanced parasitic load** on any single cell tap.

---

## 2. Pre-Pack Conservative Bench Verification Procedure

**DO NOT CONNECT A LIVE 21700 LITHIUM-ION BATTERY PACK** until every step below passes with a current-limited bench power supply!

### Step 1: Bare-Board Visual & DMM Continuity Audit (Unpowered)
1. Inspect `U3 (INA226AIDGSR)`, `R_SHUNT (1.0 mΩ 4-wire)`, `F1..F7` PPTCs, and `D1..D7` TVS diodes under magnification for solder bridges.
2. Measure resistance between `3V3` and `GND` (expect `> 5 kΩ`, no short).
3. Measure resistance between `J1 (PACK_POS_IN)` and `GND` (expect `> 100 kΩ` — open circuit aside from high-Z `VBUS` sense path).
4. Verify `J3` sense tap pinout continuity against your pack's JST-XH balance harness **with a multimeter before plugging in**. Confirm Pin 1 = `B0/PACK-`, Pin 2 = `B1`, ..., Pin 7 = `B6` (no reversed polarity!).

### Step 2: Logic-Only USB-C Bring-Up (No High Voltage Connected)
1. Disconnect `J1`, `J2`, and `J3`.
2. Connect USB-C cable (`5 V`, current-limited USB port or hub) to `J4`.
3. Measure `3V3` rail on TP1 (`3.30 V ± 0.05 V`) and `U6 LM4040` reference on TP2 (`2.048 V ± 0.005 V`).
4. Open serial monitor (`115200 baud`) and confirm JSON boot packet:
   `{"type":"boot","fw":"1.0.0","monitor_only":1,"ina226_ok":true}`
   Verify `ina226_ok:true` confirms I2C communication (`0x40`) with INA226.

### Step 3: Current-Limited Bench PSU + Resistor Ladder Simulation (No Li-Ion Pack)
1. Build a passive **4S or 6S dummy cell resistor ladder** (`4x` or `6x` `1 kΩ, 0.5 W` resistors in series) powered by a **current-limited bench PSU set to `16.80 V` (4S) or `25.20 V` (6S) with current limit strictly capped at `50 mA`**.
2. Connect bench PSU positive to `J1 PACK_POS_IN`, negative to `GND`, and tap nodes across the `1 kΩ` ladder into `J3 (B0..B4/B6)`.
3. Confirm bench PSU draws `< 25 mA` total (verifying zero short circuits and negligible sense divider draw).
4. Verify in serial JSON telemetry / CellGuard dashboard:
   - `bus_v` reads `16.80 V ± 0.05 V` (4S) or `25.20 V ± 0.05 V` (6S).
   - Every cell group reads `4.20 V ± 0.03 V` (run two-point `cal_tool` calibration if trim needed).
   - `alarm_mask == 0` and `tap_fault` is absent.
5. Verify NTC thermistors `J6`: warm `NTC1` gently with a finger or warm air gun (do not exceed `65 °C`) and confirm `temps_c[0]` tracks smoothly and `dT/dt` rises monotonically.

### Step 4: Shunt Load Verification Using Current-Limited PSU + Electronic Load
1. Keep `J3` disconnected or on resistor ladder.
2. Connect bench PSU (`15.0 V`, current limit **`5.0 A`**) to `J1 PACK_POS_IN` and connect a DC electronic load set to `2.0 A` CC mode between `J2 LOAD_POS_OUT` and `GND`.
3. Verify `current_a` reads `2.00 A` (within shunt tolerance; perform `CAL_CURR_PT1 0.0` and `CAL_CURR_PT2 2.00` via USB CLI against a calibrated DMM, then `SAVE`).
4. Step electronic load from `1.0 A` to `4.0 A` and confirm `r_dc_pack_ohm` / `rdc_step_count` tracks the PSU/wiring voltage drop without tripping false faults.

### Step 5: Live Pack Connection (Behind Commercial BMS & Inline Fuse)
1. Power down electronic load. Verify external commercial BMS is installed on the 21700 pack and main inline fuse (`F_MAIN`) is in place.
2. Connect `GND` (`PACK-`) first, then `J3` protected balance sense connector, and finally `J1 PACK_POS_IN` downstream of the commercial BMS + `F_MAIN` fuse.
3. Monitor `temp_max_c` and `cell_delta_mv` continuously for the first 60 seconds at idle before applying load.
