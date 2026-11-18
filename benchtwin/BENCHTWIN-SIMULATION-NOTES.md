# CellGuard BenchTwin Simulation & Hardware Staging Notes

## 1. Package Inventory (`benchtwin/`)
- `cellguard-benchtwin.json` — Declarative BenchTwin v1 circuit & simulation profile descriptor (70 components, 50 electrical nets, 4S/6S bench PSU load-step scenarios).
- `cellguard.btw` — Portable BenchTwin workspace bundle embedding the circuit layout, netlist, ESP32 firmware entry (`main.cpp` + `cellguard_config.h`), enclosure mesh metadata, and SHA-256 integrity checksum.
- `cellguard.net` — KiCad 8 S-expression netlist synchronized 1:1 with `hardware/cellguard.kicad_sch`.
- `BOM.csv` — Complete component bill of materials matching `hardware/BOM.csv`.
- `cellguard_enclosure.stl` — Validated 96 × 68 × 28 mm binary STL 3D-printable enclosure (192 triangles, 4× M3 internal standoffs, cutouts for `XT60` power ports, `JST-XH` 7-pin sense taps, `JST-XH` 8-pin NTC header, `USB-C`, and top Kelvin shunt cooling vent).

---

## 2. Safety & Pre-Simulation Rules
1. **Monitor-Only Architecture**: BenchTwin simulation runs **strictly non-invasive telemetry**. There are no balancing bleed switches, charge converters, or pack disconnect MOSFETs in the circuit graph.
2. **External BMS & Fuse Modeling**: When staging a virtual Li-Ion pack in BenchTwin, always include an inline series main fuse (`F_MAIN`, 40–60 A) and a commercial BMS protection block upstream of `J1 PACK_POS_IN`.
3. **Current-Limited Bring-Up First**: Begin BenchTwin testing with the `4s_21700_bench_psu` profile (`16.8 V`, current limit `50 mA` for sense verification, then `5 A` electronic load step) before running `6s_21700_high_drain` (`25.2 V`, `25 A` pulsed load).

---

## 3. Virtual Bench Pin & Signal Verification Matrix

| BenchTwin Signal | Net Name | ESP32 Pin | Expected Bench Reading (4S @ 16.8V, 10A) |
|---|---|---|---|
| Shunt Differential + | `SHUNT_P_FILT` | INA226 `IN+` (`0x40`) | `VBUS + 10.0 mV` across `1.0 mΩ` Kelvin shunt |
| Shunt Differential - | `SHUNT_N_FILT` | INA226 `IN-` (`0x40`) | `16.800 V` (`BUS_LSB = 1.25 mV`) |
| Hardware Overcurrent | `INA_ALERT` | `GPIO16` (Active Low) | `3.3 V` idle; pulls `0 V` when `I >= 45 A` |
| Multiplexed Cell Tap | `MUX_OUT` | `GPIO36` (`ADC1_CH0`) | `2.10V (B1)`, `2.10V (B2)`, `2.104V (B3)`, `2.154V (B4)` |
| 2.048 V Reference | `VREF_2V048` | MUX `CH7` | `2.048 V ± 0.005 V` (`LM4040AIM3-2.0`) |
| Thermal Probes 0–3 | `NTC0..NTC3` | `GPIO39,34,35,32` | `1.650 V` @ `25.0 °C` (`10 kΩ / 10 kΩ`) |

---

## 4. Importing into BenchTwin
1. Open [benchtwin.com](https://benchtwin.com) and import `benchtwin/cellguard.btw` (or load `cellguard-benchtwin.json` + `cellguard_enclosure.stl`).
2. Attach the virtual UART monitor to `115200 baud` and verify boot packet:
   `{"type":"boot","fw":"1.0.0","monitor_only":1,"ina226_ok":true}`.
3. Step the simulated electronic load from `2.0 A` to `18.0 A` and observe `r_dc_pack_ohm` converging via `R_dc = -ΔV / ΔI`, while `dT/dt` stays `< 2.0 °C/min`.
