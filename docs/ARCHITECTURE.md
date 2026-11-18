# CellGuard System Architecture

## 1. Design Philosophy & Safety Boundaries

CellGuard is a precision **1S–6S (4S/6S optimized) 21700 Li-Ion battery pack telemetry and health analytics instrument**. It is explicitly engineered as a **non-invasive instrumentation layer** that operates alongside an **external commercial BMS** and an **inline main fuse**:

- **Zero Actuation Surface**: No cell balancing bleed resistors/FETs, no charge controller, and no high-current pack disconnect MOSFETs exist anywhere in the schematic, PCB, firmware, or REST API (`CELLGUARD_MONITOR_ONLY = 1`).
- **Fault-Limited Sense Taps**: Every cell sense tap (`B1..B6`) and `VBUS` line enters through a `100 mA / 60 V` resettable PPTC polyfuse (`F1..F7`), clamps transients through an `SMAJ28A` TVS diode (`D1..D7`), scales via `0.1%` high-impedance dividers (`200 kΩ` to `1.1 MΩ`, `< 25 µA` draw), and clamps ADC excursions via `BAT54S` dual Schottky arrays (`D8..D10`).
- **Isolated Logic Rail**: ESP32 and analog front-end ICs run exclusively off the `5 V -> 3.3 V` (`AMS1117-3.3`) USB/isolated auxiliary rail, preventing parasitic uneven cell loading.

---

## 2. System Block Diagram

```
   [21700 Pack 4S/6S + Commercial BMS + Main Fuse]
        |                          | (B0..B6 Balance Harness)
        | PACK+                    v
   (J1 XT60-M)               (J3 JST-XH 7-Pin)
        |                          |
  [R_SHUNT 1.0mOhm]         [F1..F6 100mA PPTC]
   4-Wire Kelvin            [D1..D6 SMAJ28A TVS]
        |                          |
   (J2 XT60-F)              [0.1% High-Z Dividers]
        |                          |
  SHUNT_P / SHUNT_N         [D8..D10 BAT54S Clamp]
   + 10R/100nF RC                  |
        |                   [U4 CD74HC4051 8:1 MUX]
        v                   (CH0..5=Taps, CH6=AGND, CH7=2.048V Ref)
  [U3 INA226 16-bit]               |
   I2C (0x40) + ALERT       [U5 MCP6001 Buffer]
        |                          |
        +---- GPIO21/22/16 --------+---- GPIO36 (ADC1_CH0)
                     |
              [U1 ESP32-WROOM-32E] <--- GPIO39,34,35,32 (4x 10k NTCs)
                     |
           USB-UART 115200 JSON + NVS Calibration CLI
                     |
          [FastAPI Backend + SQLite] ---> [React+TS Dashboard at /]
```

---

## 3. Subsystem Mathematics

### 3.1 INA226 Shunt & Bus Calibration
Following TI INA226 (`SBOS547A`):
- `Current_LSB = I_max_expected / 32768` (e.g., `60 A / 32768 = 1.831 mA/bit`).
- `CAL = floor(0.00512 / (Current_LSB * R_shunt))` (`2796` / `0x0AEC` for `1.0 mΩ`, `60 A`).
- `Effective_Current_LSB = 0.00512 / (CAL * R_shunt)`.
- `Power_LSB = 25 * Effective_Current_LSB`.
- Hardware `ALERT` pin (`GPIO16` ISR) latches on shunt overvoltage (`SOL`) above `max_discharge_a`.

### 3.2 Steinhart-Hart NTC & Thermal Runaway Derivative (`dT/dt`)
Four `10 kΩ @ 25 °C` NTC thermistors in `10.0 kΩ` precision high-side dividers:
- `R_ntc = R_series * V_adc / (V_ref - V_adc)` (fault sentinels at `<= 0.015 V` short or `>= V_ref - 0.015 V` open wire).
- `1 / T_K = A + B * ln(R_ntc) + C * ln(R_ntc)^3` (`A = 1.129148e-3, B = 2.34125e-4, C = 8.76741e-8`).
- **OLS Thermal Slope (`dT/dt`)**: A 16-sample sliding-window ordinary least-squares regression computes slope in `°C/min` once span `>= 4.0 s`, rejecting single-sample ADC noise while triggering `THERMAL_RUNAWAY_WARN` (`>= 2.0 °C/min`) and `THERMAL_RUNAWAY_CRIT` (`>= 5.0 °C/min`).

### 3.3 OCV + Coulomb SoC Fusion, `R_dc`, and `SoH`
- **Trapezoidal Coulomb Counting**: `dQ_mAh = 0.5 * (I_prev + I_now) * (dt_s / 3600) * 1000`.
- **IR-Compensated OCV Estimation**: `V_ocv_est = V_cell_avg + I_pack * R_dc_cell`, mapped across a 19-breakpoint 21700 NMC/INR OCV-SoC LUT (`2.50 V = 0%` to `4.20 V = 100%`).
- **Complementary Fusion**: During load, SoC tracks Coulomb integration; after rest (`|I| < 0.15 A` for `>= 30 s`), OCV gently corrects integrator drift weighted by local `dOCV/dSoC` sensitivity.
- **Dynamic DC-IR (`R_dc = -ΔV / ΔI`)**: Captures load transitions `|ΔI| >= 1.0 A` within `<= 2.5 s`, filtering valid pack resistances with EMA (`alpha = 0.25`).
- **State of Health (`SoH`)**: Blends `65%` deep-cycle capacity retention (`Q_measured / Q_rated`) with `35%` internal-resistance growth (`100%` at `R_nom` down to `80%` at `2.0 * R_nom`).

---

## 4. Firmware–Backend Parity
`backend/analytics.py` mirrors the exact C++ constants, OCV LUT, INA226 register scaling, Steinhart-Hart parameters, OLS slope window, `R_dc` step detector, and alarm rules engine, validated across automated unit and integration tests.

---

## 5. Simulator-Independent Hardware Architecture (Wokwi Active, BenchTwin Preserved)

CellGuard decouples firmware/analytics verification from any single simulator via the canonical HAL in `simulation/adapters/common/`:
- `battery_hal_interface.h` (C++) and `battery_hal_interface.py` (Python `BatteryHALInterface`) expose read-only telemetry (`INA226`, 4x `NTC`, 1S–6S cell tap `ADC`, and non-invasive alarm outputs) while enforcing `CELLGUARD_MONITOR_ONLY = 1`.

### 5.1 Active Simulator: Wokwi (`wokwi/`)
- `wokwi/wokwi.toml` binds directly to `../firmware/.pio/build/esp32dev/firmware.bin` and `firmware.elf`.
- **Natively Supported Components**: `board-esp32-devkit-c-v4`, `wokwi-ntc-temperature-sensor` (`GPIO39/VN`, `GPIO34`, `GPIO35`, `GPIO32`), `wokwi-potentiometer` (cell-tap/bus dividers), `wokwi-led` (`GPIO17`, `GPIO18`), `wokwi-buzzer` (`GPIO19`), `wokwi-pushbutton` (`GPIO4`).
- **Unsupported Native ICs (Custom Chips + Documented Mocks)**:
  - `INA226` (and `INA219`) are not natively supported in Wokwi -> implemented via custom I2C chip `wokwi/chip-ina226.chip.json` + `.c` (`GPIO21` SDA, `GPIO22` SCL, `GPIO16` ALERT) and `WokwiCellGuardAdapter`.
  - `CD74HC4051` 8:1 MUX is not natively supported -> implemented via `wokwi/chip-cd74hc4051.chip.json` + `.c` (`GPIO25/26/27` -> `GPIO36/VP`) and software mock in `WokwiCellGuardAdapter`.
  - Full details in `simulation/documentation/COMPONENT-SUPPORT-MATRIX.md`.

### 5.2 Future BenchTwin Reactivation
All BenchTwin artifacts remain intact under `benchtwin/` (`cellguard.btw`, `cellguard-benchtwin.json`, `cellguard.net`, `BOM.csv`, `cellguard_enclosure.stl`). To reactivate BenchTwin, follow `simulation/adapters/benchtwin/README.md` and `simulation/adapters/benchtwin/benchtwin_adapter_manifest.json`.
