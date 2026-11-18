"""Generate and verify repaired 06-CELLGUARD KiCad 10.0.8 schematic, PCB, Gerbers & 3D outputs."""

from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "00-PORTFOLIO-MANAGEMENT" / "kicad-automation"))

import kicad_toolkit as kt  # noqa: E402

HW_DIR = Path(__file__).resolve().parent
BT_DIR = ROOT / "06-CELLGUARD" / "benchtwin"
LIB = "CellGuard"
PROJ = "cellguard"


def build() -> None:
    kt.write_utf8(HW_DIR / f"{PROJ}.kicad_pro", kt.build_kicad_pro(PROJ))
    kt.write_project_lib_tables(HW_DIR, LIB)

    sb = kt.SchematicBuilder(
        project_name=PROJ,
        lib_name=LIB,
        title="CellGuard 21700 Pack Telemetry & Health Monitor (1S-6S Non-Invasive)",
        company="Jagjyot Engineering Portfolio",
        rev="1.1",
        paper="A1",
    )
    sb.add_note(
        25.4,
        15.24,
        "CELLGUARD MONITOR-ONLY INSTRUMENT v1.1 (REPAIRED & VERIFIED IN KICAD 10.0.8)\n"
        "- Fixed legacy layer hash, shorted VSSOP-10/SOIC-16 pads, 3V3/GND shorts & 559 ERC errors.\n"
        "- SAFETY: Connect J1 strictly downstream of External Commercial BMS + Inline Main Fuse.",
    )

    # U1: ESP32-DevKitC-32E (30P module)
    sb.add_component(
        kt.SchComponent(
            "U1",
            "ESP32-DevKitC-32E",
            f"{LIB}:ESP32_DevKitC_30P",
            [
                kt.SchPin("1", "EN", "NC_EN", "left", "no_connect"),
                kt.SchPin("2", "VP/GPIO36", "MUX_OUT", "left"),
                kt.SchPin("3", "VN/GPIO39", "NTC0", "left"),
                kt.SchPin("4", "D34/GPIO34", "NTC1", "left"),
                kt.SchPin("5", "D35/GPIO35", "NTC2", "left"),
                kt.SchPin("6", "D32/GPIO32", "NTC3", "left"),
                kt.SchPin("7", "D33/GPIO33", "NC_D33", "left", "no_connect"),
                kt.SchPin("8", "D25/GPIO25", "MUX_S0", "left"),
                kt.SchPin("9", "D26/GPIO26", "MUX_S1", "left"),
                kt.SchPin("10", "D27/GPIO27", "MUX_S2", "left"),
                kt.SchPin("11", "D14/GPIO14", "NC_D14", "left", "no_connect"),
                kt.SchPin("12", "D12/GPIO12", "NC_D12", "left", "no_connect"),
                kt.SchPin("13", "D13/GPIO13", "NC_D13", "left", "no_connect"),
                kt.SchPin("14", "GND1", "GND", "left"),
                kt.SchPin("15", "VUSB_5V", "VUSB_5V", "left"),
                kt.SchPin("16", "3V3", "3V3", "right"),
                kt.SchPin("17", "GND2", "GND", "right"),
                kt.SchPin("18", "D15/GPIO15", "NC_D15", "right", "no_connect"),
                kt.SchPin("19", "D2/GPIO2", "NC_D2", "right", "no_connect"),
                kt.SchPin("20", "D4/GPIO4", "GPIO4", "right"),
                kt.SchPin("21", "D16/GPIO16", "INA_ALERT", "right"),
                kt.SchPin("22", "D17/GPIO17", "LED_ALARM", "right"),
                kt.SchPin("23", "D5/GPIO5", "NC_D5", "right", "no_connect"),
                kt.SchPin("24", "D18/GPIO18", "LED_STAT", "right"),
                kt.SchPin("25", "D19/GPIO19", "GPIO19", "right"),
                kt.SchPin("26", "D21/GPIO21", "I2C_SDA", "right"),
                kt.SchPin("27", "RX0", "UART_RX", "right"),
                kt.SchPin("28", "TX0", "UART_TX", "right"),
                kt.SchPin("29", "D22/GPIO22", "I2C_SCL", "right"),
                kt.SchPin("30", "D23/GPIO23", "NC_D23", "right", "no_connect"),
            ],
            mpn="ESP32-WROOM-32E-N4",
            manufacturer="Espressif",
            rating="3.3V IO / 5V USB",
        )
    )

    sb.add_component(kt.SchComponent("U2", "AMS1117-3.3", f"{LIB}:SOT-223-3_TabPin2", [
        kt.SchPin("1", "GND", "GND", "left"),
        kt.SchPin("2", "VOUT", "3V3", "right"),
        kt.SchPin("3", "VIN", "VUSB_5V", "left"),
    ], mpn="AMS1117-3.3", manufacturer="AMS", rating="3.3V / 800mA"))

    sb.add_component(kt.SchComponent("U3", "INA226AIDGSR", f"{LIB}:VSSOP-10_3x3mm_P0.5mm_R180", [
        kt.SchPin("1", "A1", "GND", "left"),
        kt.SchPin("2", "A0", "GND", "left"),
        kt.SchPin("3", "ALERT", "INA_ALERT", "left"),
        kt.SchPin("4", "SDA", "I2C_SDA", "left"),
        kt.SchPin("5", "SCL", "I2C_SCL", "left"),
        kt.SchPin("6", "VS", "3V3", "right"),
        kt.SchPin("7", "GND", "GND", "right"),
        kt.SchPin("8", "VBUS", "VBUS_SENSE", "right"),
        kt.SchPin("9", "IN-", "SHUNT_N_FILT", "right"),
        kt.SchPin("10", "IN+", "SHUNT_P_FILT", "right"),
    ], mpn="INA226AIDGSR", manufacturer="Texas Instruments", rating="36V / 16-bit I2C"))

    sb.add_component(kt.SchComponent("U4", "CD74HC4051M", f"{LIB}:SOIC-16_3.9x9.9mm_P1.27mm", [
        kt.SchPin("1", "CH4", "DIV_B5", "left"),
        kt.SchPin("2", "CH6", "AGND", "left"),
        kt.SchPin("3", "COM", "MUX_COM", "left"),
        kt.SchPin("4", "CH7", "VREF_2V048", "left"),
        kt.SchPin("5", "CH5", "DIV_B6", "left"),
        kt.SchPin("6", "INH", "GND", "left"),
        kt.SchPin("7", "VEE", "GND", "left"),
        kt.SchPin("8", "GND", "GND", "left"),
        kt.SchPin("9", "S2", "MUX_S2", "right"),
        kt.SchPin("10", "S1", "MUX_S1", "right"),
        kt.SchPin("11", "S0", "MUX_S0", "right"),
        kt.SchPin("12", "CH3", "DIV_B4", "right"),
        kt.SchPin("13", "CH0", "DIV_B1", "right"),
        kt.SchPin("14", "CH1", "DIV_B2", "right"),
        kt.SchPin("15", "CH2", "DIV_B3", "right"),
        kt.SchPin("16", "VCC", "3V3", "right"),
    ], mpn="CD74HC4051M96", manufacturer="Texas Instruments", rating="8:1 Analog MUX"))

    sb.add_component(kt.SchComponent("U5", "MCP6001T-I/OT", f"{LIB}:SOT-23-5", [
        kt.SchPin("1", "VOUT", "MUX_OUT", "left"),
        kt.SchPin("2", "VSS", "GND", "left"),
        kt.SchPin("3", "IN+", "MUX_COM", "left"),
        kt.SchPin("4", "IN-", "MUX_OUT", "right"),
        kt.SchPin("5", "VDD", "3V3", "right"),
    ], mpn="MCP6001T-I/OT", manufacturer="Microchip", rating="3.3V RRIO Buffer"))

    sb.add_component(kt.SchComponent("U6", "LM4040AIM3-2.0", f"{LIB}:SOT-23", [
        kt.SchPin("1", "K", "VREF_2V048", "left"),
        kt.SchPin("2", "A", "GND", "right"),
        kt.SchPin("3", "NC", "NC_U6", "right", "no_connect"),
    ], mpn="LM4040AIM3-2.0/NOPB", manufacturer="Texas Instruments", rating="2.048V 0.1% Ref"))

    sb.add_component(kt.SchComponent("R_SHUNT", "1.0mOhm 5W Kelvin", f"{LIB}:R_Shunt_4Wire_CSS4J_4026", [
        kt.SchPin("1", "I+", "PACK_POS_IN", "left"),
        kt.SchPin("2", "I-", "LOAD_POS_OUT", "right"),
        kt.SchPin("3", "S+", "SHUNT_SENSE_P", "left"),
        kt.SchPin("4", "S-", "SHUNT_SENSE_N", "right"),
    ], mpn="CSS4J-4026R-1L00F", manufacturer="Bourns", rating="1mOhm / 5W Kelvin"))

    sb.add_component(kt.SchComponent("J1", "PACK_POS_IN (XT60)", f"{LIB}:AMASS_XT60_Vertical", [kt.SchPin("1", "PACK+", "PACK_POS_IN", "left"), kt.SchPin("2", "GND", "GND", "right")], mpn="XT60PW-M", rating="60A / 28V"))
    sb.add_component(kt.SchComponent("J2", "LOAD_POS_OUT (XT60)", f"{LIB}:AMASS_XT60_Vertical", [kt.SchPin("1", "LOAD+", "LOAD_POS_OUT", "left"), kt.SchPin("2", "GND", "GND", "right")], mpn="XT60PW-F", rating="60A / 28V"))
    sb.add_component(kt.SchComponent("J3", "CELL_TAPS_1S-6S", f"{LIB}:PinHeader_1x07_P2.54mm", [
        kt.SchPin("1", "B0_GND", "GND", "left"),
        kt.SchPin("2", "B1", "TAP_B1_RAW", "left"),
        kt.SchPin("3", "B2", "TAP_B2_RAW", "left"),
        kt.SchPin("4", "B3", "TAP_B3_RAW", "left"),
        kt.SchPin("5", "B4", "TAP_B4_RAW", "right"),
        kt.SchPin("6", "B5", "TAP_B5_RAW", "right"),
        kt.SchPin("7", "B6", "TAP_B6_RAW", "right"),
    ], mpn="B7B-XH-A", manufacturer="JST", rating="28V / 1A Sense"))
    sb.add_component(kt.SchComponent("J4", "USB-C_UART_5V", f"{LIB}:PinHeader_1x04_P2.54mm", [
        kt.SchPin("1", "VBUS", "VUSB_5V", "left"),
        kt.SchPin("2", "GND", "GND", "left"),
        kt.SchPin("3", "TX", "UART_RX", "right"),
        kt.SchPin("4", "RX", "UART_TX", "right"),
    ], mpn="USB-C-UART-4P", rating="5V / 1A"))
    sb.add_component(kt.SchComponent("J6", "NTC_ARRAY_4CH", f"{LIB}:PinHeader_1x08_H_P2.54mm", [
        kt.SchPin("1", "NTC0", "NTC0", "left"), kt.SchPin("2", "GND0", "GND", "left"),
        kt.SchPin("3", "NTC1", "NTC1", "left"), kt.SchPin("4", "GND1", "GND", "left"),
        kt.SchPin("5", "NTC2", "NTC2", "right"), kt.SchPin("6", "GND2", "GND", "right"),
        kt.SchPin("7", "NTC3", "NTC3", "right"), kt.SchPin("8", "GND3", "GND", "right"),
    ], mpn="B8B-XH-A", manufacturer="JST", rating="3.3V NTC"))

    sb.add_component(kt.SchComponent("SW1", "CAL_MUTE_BTN", f"{LIB}:SW_SPST_SMD", [kt.SchPin("1", "1", "GPIO4", "left"), kt.SchPin("2", "2", "GND", "right")], mpn="TL3342F160QG", rating="12V / 50mA"))
    sb.add_component(kt.SchComponent("Q1", "2N7002", f"{LIB}:SOT-23", [kt.SchPin("1", "G", "GPIO19", "left"), kt.SchPin("2", "S", "GND", "left"), kt.SchPin("3", "D", "BZ_N", "right")], mpn="2N7002K", rating="60V / 300mA"))
    sb.add_component(kt.SchComponent("LS1", "Piezo_Alert_3V3", f"{LIB}:PinHeader_1x02_P2.54mm", [kt.SchPin("1", "+", "3V3", "left"), kt.SchPin("2", "-", "BZ_N", "right")], mpn="MLT-8530", rating="3.3V Piezo"))
    sb.add_component(kt.SchComponent("R_AGND", "0R_Star_Tie", f"{LIB}:SMD_0805", [kt.SchPin("1", "1", "AGND", "left"), kt.SchPin("2", "2", "GND", "right")], rating="0R Star Bridge"))

    # F1..F7 (100mA PPTC) + D1..D7 (SMAJ28A TVS)
    for idx in range(1, 7):
        sb.add_component(kt.SchComponent(f"F{idx}", "100mA_PPTC", f"{LIB}:SMD_0805", [kt.SchPin("1", "1", f"TAP_B{idx}_RAW", "left"), kt.SchPin("2", "2", f"TAP_B{idx}_FUSED", "right")], mpn="0805L010YR", rating="60V / 100mA"))
        sb.add_component(kt.SchComponent(f"D{idx}", "SMAJ28A", f"{LIB}:D_SMA", [kt.SchPin("1", "K", f"TAP_B{idx}_FUSED", "left"), kt.SchPin("2", "A", "GND", "right")], mpn="SMAJ28A", rating="28V TVS"))
    sb.add_component(kt.SchComponent("F7", "100mA_PPTC", f"{LIB}:SMD_0805", [kt.SchPin("1", "1", "PACK_POS_IN", "left"), kt.SchPin("2", "2", "VBUS_SENSE", "right")], mpn="0805L010YR", rating="60V / 100mA"))
    sb.add_component(kt.SchComponent("D7", "SMAJ28A", f"{LIB}:D_SMA", [kt.SchPin("1", "K", "VBUS_SENSE", "left"), kt.SchPin("2", "A", "GND", "right")], mpn="SMAJ28A", rating="28V TVS"))

    for dref, dnet in [("D8", "DIV_B1"), ("D9", "DIV_B3"), ("D10", "DIV_B5")]:
        sb.add_component(kt.SchComponent(dref, "BAT54S", f"{LIB}:SOT-23", [kt.SchPin("1", "A", "GND", "left"), kt.SchPin("2", "K", "3V3", "left"), kt.SchPin("3", "COM", dnet, "right")], mpn="BAT54S", rating="30V Clamp"))

    # Precision 0.1% cell dividers R1..R12
    div_vals = [("R1", "100k", 1), ("R2", "100k", 1), ("R3", "300k", 2), ("R4", "100k", 2),
                ("R5", "499k", 3), ("R6", "100k", 3), ("R7", "680k", 4), ("R8", "100k", 4),
                ("R9", "820k", 5), ("R10", "100k", 5), ("R11", "1.00M", 6), ("R12", "100k", 6)]
    for i in range(0, 12, 2):
        r_top, v_top, ch = div_vals[i]
        r_bot, v_bot, _ = div_vals[i + 1]
        sb.add_component(kt.SchComponent(r_top, f"{v_top}_0.1%", f"{LIB}:SMD_0805", [kt.SchPin("1", "1", f"TAP_B{ch}_FUSED", "left"), kt.SchPin("2", "2", f"DIV_B{ch}", "right")], rating="0.1%"))
        sb.add_component(kt.SchComponent(r_bot, f"{v_bot}_0.1%", f"{LIB}:SMD_0805", [kt.SchPin("1", "1", f"DIV_B{ch}", "left"), kt.SchPin("2", "2", "AGND", "right")], rating="0.1%"))

    extra_r = [
        ("R13", "10R", "SHUNT_SENSE_P", "SHUNT_P_FILT"),
        ("R14", "10R", "SHUNT_SENSE_N", "SHUNT_N_FILT"),
        ("R15", "4.7k", "3V3", "I2C_SDA"),
        ("R16", "4.7k", "3V3", "I2C_SCL"),
        ("R17", "10k", "3V3", "INA_ALERT"),
        ("R18", "10k", "3V3", "NTC0"),
        ("R19", "10k", "3V3", "NTC1"),
        ("R20", "10k", "3V3", "NTC2"),
        ("R21", "10k", "3V3", "NTC3"),
        ("R22", "1.0k", "3V3", "VREF_2V048"),
        ("R23", "1.0k", "LED_ALARM", "LED_A_K"),
        ("R24", "1.0k", "LED_STAT", "LED_S_K"),
    ]
    for ref, val, n1, n2 in extra_r:
        sb.add_component(kt.SchComponent(ref, val, f"{LIB}:SMD_0805", [kt.SchPin("1", "1", n1, "left"), kt.SchPin("2", "2", n2, "right")], rating="50V / 0.125W"))

    sb.add_component(kt.SchComponent("D11", "LED_RED_ALARM", f"{LIB}:SMD_0805", [kt.SchPin("1", "A", "LED_A_K", "left"), kt.SchPin("2", "K", "GND", "right")], rating="2.0V"))
    sb.add_component(kt.SchComponent("D12", "LED_CYAN_STATUS", f"{LIB}:SMD_0805", [kt.SchPin("1", "A", "LED_S_K", "left"), kt.SchPin("2", "K", "GND", "right")], rating="3.0V"))

    caps = [
        ("C1", "100nF_C0G", "SHUNT_P_FILT", "SHUNT_N_FILT"),
        ("C2", "100nF_X7R", "3V3", "GND"),
        ("C3", "10uF_16V", "VUSB_5V", "GND"),
        ("C4", "22uF_10V", "3V3", "GND"),
        ("C5", "100nF_X7R", "3V3", "GND"),
        ("C6", "100nF_X7R", "3V3", "GND"),
        ("C7", "100nF_C0G", "DIV_B1", "AGND"),
        ("C8", "100nF_C0G", "DIV_B4", "AGND"),
        ("C9", "100nF_X7R", "NTC0", "GND"),
        ("C10", "100nF_X7R", "NTC1", "GND"),
        ("C11", "100nF_X7R", "NTC2", "GND"),
        ("C12", "100nF_X7R", "NTC3", "GND"),
    ]
    for ref, val, n1, n2 in caps:
        sb.add_component(kt.SchComponent(ref, val, f"{LIB}:SMD_0805", [kt.SchPin("1", "1", n1, "left"), kt.SchPin("2", "2", n2, "right")], rating="50V"))

    for h in ("H1", "H2", "H3", "H4"):
        sb.add_component(kt.SchComponent(h, "M3_Mount", f"{LIB}:MountingHole_3.2mm_M3_Pad_Via", [kt.SchPin("1", "GND", "GND", "left")], rating="M3"))

    sb.write(HW_DIR)

    # ---------------- PCB BUILD (110.0 mm x 82.0 mm, roomy clearance for 6S tap arrays) ----------------
    pb = kt.PCBBuilder(PROJ, LIB, 110.0, 82.0, "CELLGUARD v1.1 | NON-INVASIVE PACK MONITOR", sb.root_uuid)

    fp_esp = kt.fp_dual_row_module("ESP32_DevKitC_30P", 15, 25.4)
    fp_vssop10 = kt.FootprintDef(
        "VSSOP-10_3x3mm_P0.5mm_R180",
        "smd",
        [
            kt.PadDef(p.number, p.pad_type, p.shape, -p.x, -p.y, p.w, p.h, p.drill, p.layers)
            for p in kt.fp_vssop10("VSSOP-10_3x3mm_P0.5mm").pads
        ],
        body_w=5.8,
        body_h=4.2,
        model_rel_path="Package_SO.3dshapes/VSSOP-10_3x3mm_P0.5mm.step",
    )
    fp_soic16 = kt.fp_soic_dual("SOIC-16_3.9x9.9mm_P1.27mm", 16, 1.27, 5.4, 1.5, 0.6, "Package_SO.3dshapes/SOIC-16_3.9x9.9mm_P1.27mm.step")
    fp_sot23 = kt.fp_sot23_3("SOT-23")
    fp_sot23_5 = kt.fp_sot23_5("SOT-23-5")
    fp_sot223 = kt.fp_sot223_tab("SOT-223-3_TabPin2")
    fp_shunt = kt.fp_kelvin_shunt_4wire()
    fp_xt = kt.fp_xt60("AMASS_XT60_Vertical")
    fp_h8_h = kt.FootprintDef(
        "PinHeader_1x08_H_P2.54mm",
        "through_hole",
        [
            kt.PadDef(
                str(i + 1), "thru_hole", "rect" if i == 0 else "circle",
                round((i - 3.5) * 2.54, 3), 0.0, 1.7, 1.7, 1.0, ("*.Cu", "*.Mask")
            )
            for i in range(8)
        ],
        8 * 2.54,
        2.54,
    )
    fp_h7 = kt.fp_pin_header_1xN("PinHeader_1x07_P2.54mm", 7)
    fp_h4 = kt.fp_pin_header_1xN("PinHeader_1x04_P2.54mm", 4)
    fp_h2 = kt.fp_pin_header_1xN("PinHeader_1x02_P2.54mm", 2)
    fp_0805 = kt.fp_smd_2pin("SMD_0805", 1.825, 1.025, 1.4, "Resistor_SMD.3dshapes/R_0805_2012Metric.step")
    fp_sma = kt.fp_smd_2pin("D_SMA", 3.8, 1.8, 2.1, "Diode_SMD.3dshapes/D_SMA.step")
    fp_sw = kt.fp_smd_2pin("SW_SPST_SMD", 6.5, 1.6, 1.8)
    fp_mh = kt.fp_mounting_hole()

    for ref, (mx, my) in [("H1", (4.0, 4.0)), ("H2", (106.0, 4.0)), ("H3", (106.0, 78.0)), ("H4", (4.0, 78.0))]:
        pb.add_component(kt.PcbComponent(ref, "M3_Mount", fp_mh, mx, my, 0.0, {"1": "GND"}))

    # Main ESP32 on right
    pb.add_component(kt.PcbComponent("U1", "ESP32-DevKitC-32E", fp_esp, 84.0, 38.0, 0.0, {
        "2": "MUX_OUT", "3": "NTC0", "4": "NTC1", "5": "NTC2", "6": "NTC3",
        "8": "MUX_S0", "9": "MUX_S1", "10": "MUX_S2", "14": "GND", "15": "VUSB_5V",
        "16": "3V3", "17": "GND", "20": "GPIO4", "21": "INA_ALERT", "22": "LED_ALARM",
        "24": "LED_STAT", "25": "GPIO19", "26": "I2C_SDA", "27": "UART_RX", "28": "UART_TX", "29": "I2C_SCL",
    }))

    # High-current XT60 + 4-wire Kelvin Shunt + INA226 on top-left
    pb.add_component(kt.PcbComponent("J1", "PACK_POS_IN (XT60)", fp_xt, 10.0, 18.0, 0.0, {"1": "PACK_POS_IN", "2": "GND"}))
    pb.add_component(kt.PcbComponent("R_SHUNT", "1.0mOhm 5W Kelvin", fp_shunt, 24.0, 12.0, 0.0, {"1": "PACK_POS_IN", "2": "LOAD_POS_OUT", "3": "SHUNT_SENSE_P", "4": "SHUNT_SENSE_N"}))
    pb.add_component(kt.PcbComponent("J2", "LOAD_POS_OUT (XT60)", fp_xt, 38.0, 12.0, 0.0, {"1": "LOAD_POS_OUT", "2": "GND"}))
    pb.add_component(kt.PcbComponent("U3", "INA226AIDGSR", fp_vssop10, 50.5, 18.5, 0.0, {
        "1": "GND", "2": "GND", "3": "INA_ALERT", "4": "I2C_SDA", "5": "I2C_SCL",
        "6": "3V3", "7": "GND", "8": "VBUS_SENSE", "9": "SHUNT_N_FILT", "10": "SHUNT_P_FILT",
    }))
    pb.add_component(kt.PcbComponent("F7", "100mA_PPTC", fp_0805, 19.0, 20.5, 0.0, {"1": "PACK_POS_IN", "2": "VBUS_SENSE"}))
    pb.add_component(kt.PcbComponent("D7", "SMAJ28A", fp_sma, 27.0, 20.5, 0.0, {"1": "VBUS_SENSE", "2": "GND"}))
    pb.add_component(kt.PcbComponent("R13", "10R", fp_0805, 19.0, 26.0, 0.0, {"1": "SHUNT_SENSE_P", "2": "SHUNT_P_FILT"}))
    pb.add_component(kt.PcbComponent("R14", "10R", fp_0805, 27.0, 26.0, 0.0, {"1": "SHUNT_SENSE_N", "2": "SHUNT_N_FILT"}))
    pb.add_component(kt.PcbComponent("C1", "100nF_C0G", fp_0805, 34.0, 26.0, 0.0, {"1": "SHUNT_P_FILT", "2": "SHUNT_N_FILT"}))
    pb.add_component(kt.PcbComponent("C2", "100nF_X7R", fp_0805, 58.0, 24.5, 0.0, {"1": "3V3", "2": "GND"}))

    # Analog MUX + Buffer + VREF in middle (open 10 mm channel right of U4)
    pb.add_component(kt.PcbComponent("U4", "CD74HC4051M", fp_soic16, 52.0, 42.0, 0.0, {
        "1": "DIV_B5", "2": "AGND", "3": "MUX_COM", "4": "VREF_2V048", "5": "DIV_B6", "6": "GND", "7": "GND", "8": "GND",
        "9": "MUX_S2", "10": "MUX_S1", "11": "MUX_S0", "12": "DIV_B4", "13": "DIV_B1", "14": "DIV_B2", "15": "DIV_B3", "16": "3V3",
    }))
    pb.add_component(kt.PcbComponent("U5", "MCP6001T-I/OT", fp_sot23_5, 64.5, 34.0, 0.0, {"1": "MUX_OUT", "2": "GND", "3": "MUX_COM", "4": "MUX_OUT", "5": "3V3"}))
    pb.add_component(kt.PcbComponent("U6", "LM4040AIM3-2.0", fp_sot23, 64.5, 44.0, 0.0, {"1": "VREF_2V048", "2": "GND"}))
    pb.add_component(kt.PcbComponent("C5", "100nF_X7R", fp_0805, 64.5, 50.0, 0.0, {"1": "3V3", "2": "GND"}))
    pb.add_component(kt.PcbComponent("C6", "100nF_X7R", fp_0805, 64.5, 28.0, 0.0, {"1": "3V3", "2": "GND"}))
    pb.add_component(kt.PcbComponent("R22", "1.0k", fp_0805, 64.5, 55.0, 0.0, {"1": "3V3", "2": "VREF_2V048"}))
    pb.add_component(kt.PcbComponent("R_AGND", "0R_Star_Tie", fp_0805, 42.0, 58.0, 0.0, {"1": "AGND", "2": "GND"}))

    # Balance taps J3 + F1..F6 + D1..D6 + R1..R12
    pb.add_component(kt.PcbComponent("J3", "CELL_TAPS_1S-6S", fp_h7, 7.0, 48.0, 0.0, {
        "1": "GND", "2": "TAP_B1_RAW", "3": "TAP_B2_RAW", "4": "TAP_B3_RAW", "5": "TAP_B4_RAW", "6": "TAP_B5_RAW", "7": "TAP_B6_RAW",
    }))
    for idx in range(1, 7):
        y_row = 32.5 + (idx - 1) * 5.6
        pb.add_component(kt.PcbComponent(f"F{idx}", "100mA_PPTC", fp_0805, 14.0, y_row, 0.0, {"1": f"TAP_B{idx}_RAW", "2": f"TAP_B{idx}_FUSED"}))
        pb.add_component(kt.PcbComponent(f"D{idx}", "SMAJ28A", fp_sma, 21.0, y_row, 0.0, {"1": f"TAP_B{idx}_FUSED", "2": "GND"}))
        pb.add_component(kt.PcbComponent(f"R{2*idx-1}", "TOP_0.1%", fp_0805, 27.5, y_row, 0.0, {"1": f"TAP_B{idx}_FUSED", "2": f"DIV_B{idx}"}))
        pb.add_component(kt.PcbComponent(f"R{2*idx}", "100k_0.1%", fp_0805, 34.5, y_row, 0.0, {"1": f"DIV_B{idx}", "2": "AGND"}))

    pb.add_component(kt.PcbComponent("D8", "BAT54S", fp_sot23, 42.5, 31.5, 0.0, {"1": "GND", "2": "3V3", "3": "DIV_B1"}))
    pb.add_component(kt.PcbComponent("D9", "BAT54S", fp_sot23, 42.5, 38.5, 0.0, {"1": "GND", "2": "3V3", "3": "DIV_B3"}))
    pb.add_component(kt.PcbComponent("D10", "BAT54S", fp_sot23, 42.5, 45.5, 0.0, {"1": "GND", "2": "3V3", "3": "DIV_B5"}))
    pb.add_component(kt.PcbComponent("C7", "100nF_C0G", fp_0805, 42.0, 52.0, 0.0, {"1": "DIV_B1", "2": "AGND"}))
    pb.add_component(kt.PcbComponent("C8", "100nF_C0G", fp_0805, 42.0, 64.0, 0.0, {"1": "DIV_B4", "2": "AGND"}))

    # USB-C UART, LDO, NTC array, UI/Alarm
    pb.add_component(kt.PcbComponent("J4", "USB-C_UART_5V", fp_h4, 103.0, 38.0, 0.0, {"1": "VUSB_5V", "2": "GND", "3": "UART_RX", "4": "UART_TX"}))
    pb.add_component(kt.PcbComponent("U2", "AMS1117-3.3", fp_sot223, 86.0, 69.0, 0.0, {"1": "GND", "2": "3V3", "3": "VUSB_5V"}))
    pb.add_component(kt.PcbComponent("C3", "10uF_16V", fp_0805, 76.0, 74.5, 0.0, {"1": "VUSB_5V", "2": "GND"}))
    pb.add_component(kt.PcbComponent("C4", "22uF_10V", fp_0805, 95.0, 72.0, 0.0, {"1": "3V3", "2": "GND"}))
    pb.add_component(kt.PcbComponent("J6", "NTC_ARRAY_4CH", fp_h8_h, 56.0, 76.0, 0.0, {
        "1": "NTC0", "2": "GND", "3": "NTC1", "4": "GND", "5": "NTC2", "6": "GND", "7": "NTC3", "8": "GND",
    }))
    for idx in range(4):
        x_ntc = 47.0 + idx * 5.5
        pb.add_component(kt.PcbComponent(f"R{18 + idx}", "10k", fp_0805, x_ntc, 69.0, 0.0, {"1": "3V3", "2": f"NTC{idx}"}))
        pb.add_component(kt.PcbComponent(f"C{9 + idx}", "100nF_X7R", fp_0805, x_ntc, 64.0, 0.0, {"1": f"NTC{idx}", "2": "GND"}))

    pb.add_component(kt.PcbComponent("R15", "4.7k", fp_0805, 58.0, 12.0, 0.0, {"1": "3V3", "2": "I2C_SDA"}))
    pb.add_component(kt.PcbComponent("R16", "4.7k", fp_0805, 64.0, 12.0, 0.0, {"1": "3V3", "2": "I2C_SCL"}))
    pb.add_component(kt.PcbComponent("R17", "10k", fp_0805, 70.0, 12.0, 0.0, {"1": "3V3", "2": "INA_ALERT"}))
    pb.add_component(kt.PcbComponent("SW1", "CAL_MUTE_BTN", fp_sw, 80.0, 10.0, 0.0, {"1": "GPIO4", "2": "GND"}))
    pb.add_component(kt.PcbComponent("Q1", "2N7002", fp_sot23, 92.0, 10.0, 0.0, {"1": "GPIO19", "2": "GND", "3": "BZ_N"}))
    pb.add_component(kt.PcbComponent("LS1", "Piezo_Alert_3V3", fp_h2, 101.0, 14.0, 0.0, {"1": "3V3", "2": "BZ_N"}))
    pb.add_component(kt.PcbComponent("R23", "1.0k", fp_0805, 68.0, 62.5, 0.0, {"1": "LED_ALARM", "2": "LED_A_K"}))
    pb.add_component(kt.PcbComponent("D11", "LED_RED_ALARM", fp_0805, 73.5, 62.5, 0.0, {"1": "LED_A_K", "2": "GND"}))
    pb.add_component(kt.PcbComponent("R24", "1.0k", fp_0805, 68.0, 67.5, 0.0, {"1": "LED_STAT", "2": "LED_S_K"}))
    pb.add_component(kt.PcbComponent("D12", "LED_CYAN_STATUS", fp_0805, 73.5, 67.5, 0.0, {"1": "LED_S_K", "2": "GND"}))

    kt.sync_pcb_with_schematic(sb, pb)
    overlaps = kt.check_courtyards(pb)
    assert not overlaps, f"Courtyard overlaps: {overlaps}"

    # High-current 50A Kelvin main bus traces + clean B.Cu GND escape bus for BAT54S clamp array D8..D10
    pb.add_track("PACK_POS_IN", 3.2, [pb.pad_abs_xy("J1", "1"), pb.pad_abs_xy("R_SHUNT", "1")], "F.Cu")
    pb.add_track("LOAD_POS_OUT", 3.2, [pb.pad_abs_xy("R_SHUNT", "2"), pb.pad_abs_xy("J2", "1")], "F.Cu")
    for d_ref in ("D8", "D9", "D10"):
        dx, dy = pb.pad_abs_xy(d_ref, "1")
        pb.add_track("GND", 0.25, [(dx, dy), (39.2, dy)], "F.Cu")
        pb.add_via("GND", 39.2, dy, 0.7, 0.35)
    pb.add_track("GND", 0.30, [(39.2, 44.55), (39.2, 30.55)], "B.Cu")

    router = kt.AutoRouter2Layer(pb, grid_mm=0.5, clearance_mm=0.20)
    route_res = router.route_all(net_widths={
        "VUSB_5V": 0.5,
        "3V3": 0.4,
        "AGND": 0.4,
    })
    print("CellGuard AutoRouter failed list:", route_res["failed"])
    pb.write(HW_DIR)

    summary = kt.build_and_verify_project(HW_DIR, PROJ, gerber_dir=HW_DIR / "gerbers", models_out_dir=HW_DIR / "3d-models")
    print("CellGuard KiCad Summary:", summary)

    g_dir = HW_DIR / "gerbers"
    for src, dst in [
        ("cellguard-F_SilkS.gto", "cellguard-F_Silkscreen.gto"),
        ("cellguard-B_SilkS.gbo", "cellguard-B_Silkscreen.gbo"),
        ("cellguard-PTH.drl", "cellguard.drl"),
    ]:
        if (g_dir / src).exists():
            shutil.copy2(g_dir / src, g_dir / dst)

    kt.run_cli(
        [
            "sch", "export", "bom",
            "--fields", "Reference,Value,Footprint,MPN,Manufacturer,Rating,QUANTITY",
            "--labels", "Designator,Value,Footprint,MPN,Manufacturer,Rating,Qty",
            "--output", str(HW_DIR / "BOM-kicad.csv"),
            str(HW_DIR / f"{PROJ}.kicad_sch"),
        ],
        check=True,
    )
    if summary["erc_violations"] or summary["drc_violations"] or summary["drc_unconnected"] or summary["drc_parity_issues"]:
        raise SystemExit(2)


if __name__ == "__main__":
    build()
