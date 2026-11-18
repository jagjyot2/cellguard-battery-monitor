# Wokwi Simulation Setup for CellGuard

**Wokwi** is the active firmware simulator for CellGuard (`board-esp32-devkit-c-v4`), paired with the simulator-independent HAL in `simulation/`. The original BenchTwin digital-twin package remains preserved in `benchtwin/`.

## 1. Build Firmware with PlatformIO

```bash
cd firmware
pio run
```

This generates:
- `firmware/.pio/build/esp32dev/firmware.bin`
- `firmware/.pio/build/esp32dev/firmware.elf`

Both are referenced directly by `wokwi/wokwi.toml`.

## 2. Run in Wokwi (VS Code Extension or Wokwi CLI)

### Option A: VS Code Wokwi Extension
1. Install the **Wokwi Simulator** extension in VS Code.
2. Open the `06-CELLGUARD/wokwi/` folder or press `F1` -> `Wokwi: Start Simulator`.

### Option B: Wokwi CLI (Headless / CI)
1. Set your Wokwi CLI token in your environment:
   ```bash
   export WOKWI_CLI_TOKEN="wk_..."   # PowerShell: $env:WOKWI_CLI_TOKEN="wk_..."
   ```
2. Compile the custom Wokwi chips (`chip-ina226.chip.c` and `chip-cd74hc4051.chip.c` -> `.chip.wasm`) or run via Wokwi CLI:
   ```bash
   wokwi-cli wokwi --timeout 10000
   ```

## 3. Native vs. Custom/Mocked Components

- **Natively Supported**: `board-esp32-devkit-c-v4`, `wokwi-ntc-temperature-sensor` (`GPIO39/VN`, `GPIO34`, `GPIO35`, `GPIO32`), `wokwi-potentiometer` (cell-tap/bus analog simulation), `wokwi-led` (`GPIO17`, `GPIO18`), `wokwi-buzzer` (`GPIO19`), `wokwi-pushbutton` (`GPIO4`).
- **Unsupported Natively (Custom Chips + Software Mocks)**:
  - `INA226` (`0x40`, `GPIO21` SDA, `GPIO22` SCL, `GPIO16` ALERT) -> `chip-ina226.chip.json`/`.c`
  - `CD74HC4051` 8:1 MUX (`GPIO25/26/27` -> `GPIO36/VP`) -> `chip-cd74hc4051.chip.json`/`.c`
  See [`../simulation/documentation/COMPONENT-SUPPORT-MATRIX.md`](../simulation/documentation/COMPONENT-SUPPORT-MATRIX.md) for full details.
