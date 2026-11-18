# Manufacturing Readiness Report — `06-CELLGUARD` (`cellguard`)

- **Board Reviewed**: [`cellguard.kicad_pcb`](cellguard.kicad_pcb) / [`cellguard.kicad_sch`](cellguard.kicad_sch)
- **Audit Date**: `2026-11-18`
- **Release Decision**: **`HOLD — CONDITIONAL ON COPPER WEIGHT & CONNECTOR UPGRADE`** (cleanest overall electrical/Kelvin topology in the portfolio, but high-current bus requires `2 oz` Cu / polygon pours for `50–60 A` operation and keyed `2.50 mm` JST-XH footprints)

---

## 1. Board Specifications & DRC/ERC Summary (Observed Live)

| Parameter | Measured Value | Status / Observation |
|---|---|---|
| Dimensions (`Edge.Cuts`) | `110.0 x 82.0 mm`, thickness `1.6 mm`, `ENIG` | `VERIFIED` |
| Copper Stackup | `2` Layers (`F.Cu`, `B.Cu`), `1 oz` Cu default | **`VERIFIED WITH LIMITATIONS`** (`1 oz` insufficient for unassisted `50 A` on `3.2 mm` trace) |
| Placed Symbols / Footprints | `75` schematic symbols / `75` PCB footprints (`71` parts + `H1..H4`) | `VERIFIED` |
| KiCad `10.0.8` ERC (`--severity-all`) | `0` Errors, `0` Warnings (exit `0`) | `VERIFIED WITH LIMITATIONS` |
| KiCad `10.0.8` DRC (`--schematic-parity`) | `0` Violations, `0` Unconnected Pads, `0` Parity Issues (exit `0`) | `VERIFIED WITH LIMITATIONS` |
| Mounting Holes (`H1..H4`) | `(4,4), (106,4), (106,78), (4,78)` (`3.2 mm` drill, `5.2 mm` pad, **`1.40 mm`** pad-to-edge clearance) | `VERIFIED` |
| Vias & Drills | `120` vias (`0.70 / 0.35 mm`); component drills: `1.00`, `3.20`, `3.80 mm` | `VERIFIED` (`cellguard-PTH.drl`) |
| `B.Cu` Ground Pour (`GND`) | `1` contiguous `filled_polygon` (`0.25 mm` clearance, `0.35 mm` thermal bridge) + `R_AGND` `0R_Star_Tie` | **`VERIFIED`** |
| Gerber / Drill Files (`hardware/gerbers/`) | Complete 2-layer Gerber set (`9` Gerber + `.gbrjob` + `cellguard-PTH.drl`, `cellguard-NPTH.drl` + PDF drill maps) + duplicate legacy `cellguard.drl` (`2887 B`, identical size to `cellguard-PTH.drl`) & `DRC-REPORT.txt` alongside `cellguard_{erc,drc}.{txt,json}` | **`VERIFIED WITH LIMITATIONS`** (remove stale duplicate `cellguard.drl` before fab upload) |
| BOM Integrity | `BOM.csv`: `70` rows (grouped passives); `BOM-kicad.csv`: `75` per-refdes rows | `VERIFIED` |

---

## 2. Electrical, Kelvin Shunt & Measurement Verification

| Circuit / Net | Measured PCB Routing | Engineering Assessment | Status |
|---|---|---|---|
| `PACK_POS_IN` (`J1 XT60` -> `R_SHUNT`) | `[0.25, 3.20] mm`, `21.8 mm` length (`3.2 mm` main trunk + `0.25 mm` tap to `F7/R13`) | `3.2 mm` `1 oz` Cu carries `~6.8 A` @ `20 °C` rise (`~9.5 A` @ `35 °C` rise). At `50–60 A` continuous, copper temperature rise becomes severe without `2 oz` Cu, `B.Cu` parallel copper pours, and exposed solder-mask copper bar reinforcement. | **`VERIFIED WITH LIMITATIONS`** |
| `LOAD_POS_OUT` (`R_SHUNT` -> `J2 XT60`) | `[3.20] mm`, `10.1 mm` length | Same `~6.8–9.5 A` `1 oz` continuous limit; upgrade to dual-layer pour for `50–60 A`. | **`VERIFIED WITH LIMITATIONS`** |
| `SHUNT_SENSE_P/N` & `SHUNT_P/N_FILT` | `[0.25]` (`16.2`, `13.2 mm`) & `[0.22, 0.25]` (`40.8`, `30.0 mm`) | Dedicated inner Kelvin sense pads `3` and `4` on `R_Shunt_4Wire_CSS4J_4026` (`1.0 mOhm 5W`) into `U3 INA226AIDGSR` (`0x40`) with differential RC filtering (`R13/R14 = 10R`). | **`VERIFIED`** |
| Cell Tap Dividers (`R1..R12`, `F1..F7`, `D1..D6`) | `0.1%` resistors (`100k/100k` 2:1, `300k/100k` 4:1, `499k/100k` 5.99:1, `680k/100k` 7.8:1, `820k/100k` 9.2:1, `1.0M/100k` 11:1) | Every cell tap scales `<= 3.3 V` into `U4 CD74HC4051` (`VCC = 3.3 V`) with `100 mA` PPTC fuses (`F1..F6`), `SMAJ28A` TVS (`D1..D6`), and `BAT54S` rail clamps (`D8..D10`). | **`VERIFIED`** |
| `U5 MCP6001` Buffer + `U6 LM4040-2.0` Ref | Analog MUX output buffer & `2.048 V` precision reference on isolated `AGND` | Clean star-ground tie (`R_AGND = 0R`) separation between noisy digital `GND` and `AGND`. | **`VERIFIED`** |

---

## 3. Footprint & Connector Review

- **`R_SHUNT` (`R_Shunt_4Wire_CSS4J_4026`) — `VERIFIED`**: True 4-terminal Bourns CSS4J-4026 geometry (`±4.2, -1.2 mm` force pads; inner sense pads at `±1.6, +2.0 mm`); confirm Bourns CSS4J-4026 land pattern tolerance prior to stencil order.
- **`J3` (`CELL_TAPS_1S-6S`) & `J6` (`NTC_ARRAY_4CH`) — `PROVISIONAL`**: Placed as `PinHeader_1x07_P2.54mm` and `PinHeader_1x08_H_P2.54mm` instead of genuine keyed `2.50 mm` JST-XH housings (`0.28 mm` cumulative pitch drift across 8 pins).
- **`J4` (`USB-C_UART_5V`) — `PROVISIONAL`**: Placed as `PinHeader_1x04_P2.54mm` (external USB-UART adapter header), NOT a board-mounted USB Type-C receptacle.
- **`U3` (`INA226AIDGSR`) & `U4` (`CD74HC4051M`) — `VERIFIED`**: Standard `VSSOP-10_3x3mm_P0.5mm` and `SOIC-16_3.9x9.9mm_P1.27mm` IPC footprints.

## 4. Required Actions Before Fabrication
1. Convert `PACK_POS_IN` and `LOAD_POS_OUT` to `2 oz` dual-layer heavy copper polygons with exposed solder-mask solder-wick/busbar strips (or rate board strictly to `<= 10 A` if ordered in `1 oz` Cu).
2. Replace `J3` and `J6` with genuine keyed `2.50 mm` JST-XH shrouded footprints to prevent balance-plug misinsertion (reverse cell polarity hazard) and pitch binding.
3. Delete duplicate `gerbers/cellguard.drl` so only `cellguard-PTH.drl` and `cellguard-NPTH.drl` are zipped for fab upload.
