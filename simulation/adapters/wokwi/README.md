# Wokwi Adapter for CellGuard

This adapter connects CellGuard's simulator-independent `BatteryHALInterface` (`simulation/adapters/common/battery_hal_interface.py`) to Wokwi simulations (`wokwi/diagram.json` & `wokwi/wokwi.toml`) and scenario replay files in `simulation/scenarios/`.

## Component Mapping

| Subsystem | Wokwi Representation | Notes |
|---|---|---|
| MCU | `board-esp32-devkit-c-v4` | Native Wokwi ESP32-WROOM-32E target |
| INA226 (0x40) | Custom I2C chip `chip-ina226` | `wokwi/chip-ina226.chip.json` + `.c` (`GPIO21` SDA, `GPIO22` SCL, `GPIO16` ALERT) |
| NTC Thermistors (x4) | `wokwi-ntc-temperature-sensor` | Native Wokwi probes on `GPIO39`, `GPIO34`, `GPIO35`, `GPIO32` |
| Cell Tap / Bus Dividers | `wokwi-potentiometer` + MUX stub | `GPIO36` ADC1_CH0 + `GPIO25/26/27` (`S0/S1/S2`) |
| Alarm Indicators | `wokwi-led` | `GPIO17` (Red Alarm), `GPIO18` (Green Status) |

> **Safety Boundary**: Monitor-only (`CELLGUARD_MONITOR_ONLY=1`). No charging, balancing, or FET-switching pins exist.
