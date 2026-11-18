# CellGuard Simulation Component Support Matrix

This document explicitly records which hardware components in CellGuard (`firmware/include/cellguard_config.h` & `hardware/BOM.csv`) are **natively supported** by Wokwi versus **unsupported natively** and therefore implemented via custom Wokwi chips or documented software mocks.

> **Engineering Policy**: Unsupported ICs are **NEVER** silently substituted with unrelated parts. Every custom chip or software mock is explicitly declared here and in `wokwi/diagram.json`.

## 1. Wokwi Component Support Matrix

| CellGuard Hardware Component | Purpose & Pins | Wokwi Native Support | Wokwi Implementation / Mock Strategy |
|---|---|---|---|
| **ESP32-WROOM-32E** (`U1`) | Main telemetry MCU (`I2C`, `ADC1`, `NVS`) | **Supported** (`board-esp32-devkit-c-v4`) | Native ESP32 simulation running `firmware/.pio/build/esp32dev/firmware.elf` |
| **10kΩ NTC Thermistors x4** (`TH1..TH4`) | Pack & busbar temp (`GPIO39`, `GPIO34`, `GPIO35`, `GPIO32`) | **Supported** (`wokwi-ntc-temperature-sensor`) | Native Wokwi NTC probes wired to `GPIO39/34/35/32` |
| **Cell Tap / Bus Analog Dividers** (`R_div`) | Scaled pack & cell-tap analog voltages (`GPIO36`) | **Supported** (`wokwi-potentiometer`) | Native Wokwi potentiometers simulating divider tap voltages |
| **Alarm & Status LEDs** (`D_ALARM`, `D_STATUS`) | Red hardware alarm (`GPIO17`), Green heartbeat (`GPIO18`) | **Supported** (`wokwi-led`) | Native Wokwi LEDs with series resistors |
| **Piezo Buzzer** (`LS1`) | Low-current audible alert (`GPIO19`) | **Supported** (`wokwi-buzzer`) | Native Wokwi piezo buzzer (optional in minimal diagram) |
| **Calibration / Mute Button** (`SW1`) | Alarm mute & NVS cal ack (`GPIO4`) | **Supported** (`wokwi-pushbutton`) | Native Wokwi pushbutton |
| **TI INA226AIDGSR** (`U3`, I2C `0x40`) | 16-bit shunt/bus voltage & current + `ALERT` (`GPIO21`, `GPIO22`, `GPIO16`) | **UNSUPPORTED NATIVELY** (neither `INA226` nor `INA219` is built-in) | **Custom Wokwi I2C Chip**: `wokwi/chip-ina226.chip.json` + `wokwi/chip-ina226.chip.c` implementing TI `0x40` registers (`0x00`..`0x07`, `0xFE`=`0x5449`, `0xFF`=`0x2260`) & open-drain `ALERT` on `GPIO16`, paired with `WokwiCellGuardAdapter` |
| **CD74HC4051 8:1 Analog MUX** (`U4`) + **MCP6001** (`U5`) + **LM4040 2.048V** (`U6`) | Multiplexed `B1..B6`, `AGND`, `VREF` on `GPIO36` via `S0=25, S1=26, S2=27` | **UNSUPPORTED NATIVELY** (`CD74HC4051` not built-in) | **MUX Stub + Software Mock**: `wokwi/chip-cd74hc4051.chip.json` + `.c` stub (or direct `wokwi-potentiometer` tap feed into `GPIO36` with `S0..S2` monitored) + documented software mock in `WokwiCellGuardAdapter.read_cell_taps()` |
| **100 mA PPTC Polyfuses (`F1..F7`) & SMAJ28A TVS (`D1..D7`) & BAT54S (`D8..D10`)** | Sense-lead overcurrent & transient protection | **Not simulated** (passive protection) | Physical PCB safety components verified via KiCad DRC & `hardware/SAFETY-AND-TEST-PROCEDURE.md` |

## 2. Safety Boundary Verification

- `CELLGUARD_MONITOR_ONLY = 1`
- `CELLGUARD_BALANCING_SUPPORTED = 0`
- `CELLGUARD_CHARGING_SUPPORTED = 0`
- `CELLGUARD_FET_SWITCHING_SUPPORTED = 0`
- External commercial BMS and inline main fuse are mandatory in both physical and simulated topologies.
