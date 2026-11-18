# CellGuard — Intelligent 21700 Li-Ion Battery Pack Monitor & Health Analytics

[![License: MIT](https://img.shields.io/badge/License-MIT-cyan.svg)](./LICENSE)
[![PlatformIO](https://img.shields.io/badge/Firmware-ESP32%20PlatformIO-emerald.svg)](./firmware/platformio.ini)
[![FastAPI + React](https://img.shields.io/badge/Dashboard-FastAPI%20%2B%20React%20TS-blue.svg)](./backend/main.py)
[![Safety](https://img.shields.io/badge/Safety-Monitor%20Only%20(Use%20External%20BMS)-amber.svg)](./hardware/SAFETY-AND-TEST-PROCEDURE.md)

**CellGuard** (`cellguard-battery-monitor`) is an end-to-end embedded + hardware + analytics platform for monitoring **1S–6S 21700 Li-Ion battery packs** (optimized for **4S 14.8 V** and **6S 22.2 V** packs). It combines a KiCad 8 Kelvin-shunt instrumentation PCB, modular ESP32 PlatformIO C++ firmware, a BenchTwin digital-twin staging package, a FastAPI + SQLite analytics backend, and a dark-mode React + TypeScript telemetry dashboard.

> **CRITICAL SAFETY NOTICE**  
> **CellGuard is strictly a NON-INVASIVE, READ-ONLY telemetry and health analytics instrument.**  
> It **MUST ONLY** be used **alongside an external commercial BMS and an inline main fuse**.  
> CellGuard implements **NO cell balancing**, **NO battery charging**, and **NO high-current MOSFET switching**.  
> Review [`hardware/SAFETY-AND-TEST-PROCEDURE.md`](./hardware/SAFETY-AND-TEST-PROCEDURE.md) before applying power.

---

## Key Capabilities

- **Precision Current & Bus Sensing (`INA226`)**: 16-bit I2C shunt/bus monitoring across a **4-wire Kelvin `1.0 mΩ` shunt** with datasheet `CAL` register math, hardware `ALERT` interrupt (`GPIO16`), and 2-point gain/offset calibration.
- **Protected 1S–6S Cell Tap Monitoring**: `100 mA` PPTC polyfuses (`F1..F6`), `SMAJ28A` TVS surge clamping (`D1..D6`), `0.1%` high-impedance dividers, `BAT54S` ADC clamps, and an `8:1` analog MUX (`CD74HC4051` + `2.048 V` `LM4040` precision reference) with bus-sum cross-check.
- **4-Channel Thermal Runaway Array**: Steinhart-Hart NTC thermistor probes (`GPIO39/34/35/32`) with open/short wire fault detection and sliding-window OLS `dT/dt` (`°C/min`) thermal runaway derivative alarms.
- **Battery Health Analytics Engine**:
  - **OCV + Coulomb SoC Fusion**: Trapezoidal mAh/Wh integrator fused during rest with an IR-compensated 19-point 21700 NMC/INR OCV lookup table.
  - **Dynamic DC Internal Resistance (`R_dc = -ΔV / ΔI`)**: Automatic load-step resistance estimator tracking pack and per-cell impedance growth.
  - **State of Health (`SoH %`)**: Combines capacity retention fade and internal resistance growth.
- **Interactive Dashboard & CLI Calibration**: Dark-mode React + TypeScript UI served directly at `/`, 4S/6S bench discharge replay, configurable alarm rules, CSV history export, and `calibration_cli.py` + ESP32 NVS CRC16-protected serial calibration.

---

## Repository Structure

```text
06-CELLGUARD/
├── firmware/                  # PlatformIO ESP32 C++ firmware (INA226, NTC, MUX, Analytics, NVS CLI)
├── backend/                   # FastAPI REST API, SQLite DB, dataset replay & built dashboard assets
├── dashboard/                 # React + TypeScript + Vite dark-mode dashboard source
├── hardware/                  # KiCad 8 schematic, PCB, netlist, BOM, Gerbers & Safety Guide
├── benchtwin/                 # BenchTwin .btw workspace, JSON circuit, netlist, BOM & 3D STL enclosure
├── tests/                     # Pytest verification suite (INA226, SoC/SoH/R_dc, thermal, API/CLI)
├── docs/ARCHITECTURE.md       # Hardware/firmware math & system design specification
├── calibration_cli.py         # Two-point shunt & voltage divider calibration utility
└── ROADMAP.md                 # Engineering milestones & future roadmap
```

---

## Quick Start

### 1. Run Backend & Web Dashboard
```bash
pip install -r requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8006
```
Open **`http://127.0.0.1:8006/`** in your browser.

*(Optional)* Rebuild the React + TypeScript dashboard frontend into `backend/static/`:
```bash
cd dashboard
npm install
npm run build
```

### 2. Build ESP32 Firmware (PlatformIO)
```bash
cd firmware
pio run
```

### 3. Run Calibration CLI Utility
```bash
python calibration_cli.py --series-cells 4 --capacity-mah 5000 --shunt-mohm 1.0 \
  --curr-meas1 0.02 --curr-ref1 0.00 --curr-meas2 19.85 --curr-ref2 20.00
```

### 4. Run Automated Test Suite
```bash
pytest -v
```

---

## Documentation
- [Hardware Safety & Conservative Bench Test Procedure](./hardware/SAFETY-AND-TEST-PROCEDURE.md)
- [PCB Assembly & Calibration Guide](./hardware/ASSEMBLY-GUIDE.md)
- [System Architecture & Analytics Math](./docs/ARCHITECTURE.md)
- [BenchTwin Simulation Notes](./benchtwin/BENCHTWIN-SIMULATION-NOTES.md)
- [Development Roadmap](./ROADMAP.md)

## License
Released under the [MIT License](./LICENSE).
