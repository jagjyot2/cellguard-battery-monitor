# BenchTwin Adapter (Preserved for Future Reactivation)

The original BenchTwin digital-twin staging package in `../../benchtwin/` is **preserved intact** (`.btw`, `cellguard-benchtwin.json`, `cellguard.net`, `BOM.csv`, `cellguard_enclosure.stl`, `BENCHTWIN-SIMULATION-NOTES.md`) while **Wokwi** serves as the active firmware simulator.

## Reactivating BenchTwin in the Future

1. Open `../../benchtwin/cellguard.btw` in BenchTwin or load `../../benchtwin/cellguard-benchtwin.json` via the BenchTwin CLI/runtime.
2. Implement or attach a BenchTwin runner against `simulation/adapters/common/battery_hal_interface.py` (`BatteryHALInterface`) using the pin and net mappings in `benchtwin_adapter_manifest.json`.
3. Build the ESP32 firmware with `cd firmware && pio run` and point BenchTwin's `firmware_entry` (`../firmware/src/main.cpp`) or compiled ELF to the active target.
4. Verify all safety invariants (`NON_INVASIVE_MONITOR_ONLY`, external commercial BMS + inline main fuse) remain enforced.
