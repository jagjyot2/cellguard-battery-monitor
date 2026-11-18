# CellGuard Development Roadmap

## Phase 1: Core Embedded Firmware & Precision Drivers (Completed)
- [x] PlatformIO ESP32 project (`esp32dev`, `-Wall -Wextra -Werror=return-type`, zero-error firmware binary).
- [x] `INA226Driver` with datasheet calibration math, signed/unsigned register decoding, and hardware `ALERT` interrupt ISR.
- [x] `NTCArray` 4-channel Steinhart-Hart temperature acquisition with open/short detection and sliding OLS `dT/dt` thermal runaway detector.
- [x] `CellTapMonitor` 1S–6S multiplexed divider acquisition (`CD74HC4051` + `2.048 V` precision reference + `AGND` auto-zero + bus-sum cross-check).
- [x] `BatteryAnalytics` engine: 21700 NMC/INR OCV-Coulomb SoC fusion, `R_dc = dV/dI` load-step estimator, capacity + impedance `SoH (%)`, and configurable alarms.
- [x] `CalTool` non-blocking serial CLI with CRC16-protected ESP32 NVS persistence.

## Phase 2: Hardware PCB, Protection & BenchTwin Package (Completed)
- [x] KiCad 8 schematic, 2-layer PCB, netlist, and BOM (`70` components, `50` nets).
- [x] Kelvin 4-wire `1.0 mΩ` shunt layout with symmetrical inner differential routing + RC filtering.
- [x] Sense-tap `100 mA` PPTC polyfuses + `SMAJ28A` TVS diodes + `BAT54S` ADC clamps.
- [x] RS-274X Gerbers, Excellon drill file, and DRC clean verification report (`0` errors).
- [x] BenchTwin workspace export (`cellguard.btw`, `cellguard-benchtwin.json`, `cellguard_enclosure.stl`, simulation notes).
- [x] Conservative current-limited bench bring-up & safety documentation.

## Phase 3: Analytics Backend, Web Dashboard & Verification (Completed)
- [x] FastAPI REST API + SQLite telemetry persistence + CSV export + built-in 4S/6S dataset replay.
- [x] Dark-mode React + TypeScript dashboard served directly at `/`.
- [x] Standalone `calibration_cli.py` supporting live REST push, USB serial push, and offline calculation.
- [x] Automated `pytest` suite (`test_ina226_math.py`, `test_soc_soh_analytics.py`, `test_thermal_alarms.py`, `test_api_and_calibration.py`).

## Phase 4: Future Extensions (v1.1 / v2.0)
- [ ] Live USB-UART-to-WebSocket streaming daemon bridge inside `backend/` for plug-and-play bench telemetry ingestion.
- [ ] Isolated CAN-FD (`TWAI` + `ISO1042`) telemetry broadcast for UAV / rover powertrains.
- [ ] Optional MicroSD black-box `.csv` flight/drive logging alongside NVS calibration.
- [ ] Expanded cell chemistry LUT selector (`21700 NMC`, `LFP 3.2V`, `LTO 2.4V`) while maintaining strict monitor-only isolation.
