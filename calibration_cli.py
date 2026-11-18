#!/usr/bin/env python3
"""CellGuard Two-Point Shunt & Voltage Divider Calibration CLI Utility.

Computes exact INA226 register constants (Current_LSB, CAL, Power_LSB) and
two-point linear calibration coefficients (gain, offset) for current shunt,
bus voltage, and 1S-6S sense-tap voltage dividers. Can emit ESP32 NVS CLI
commands, push calibration directly to a running CellGuard FastAPI server, or
transmit commands over USB-UART to an attached ESP32.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, Any

from backend.analytics import (
    DEFAULT_DIVIDER_RATIOS,
    compute_ina226_calibration_params,
    compute_two_point_calibration,
)


def run_calibration_calc(args: argparse.Namespace) -> Dict[str, Any]:
    r_shunt_ohm = args.shunt_mohm / 1000.0
    ina_math = compute_ina226_calibration_params(r_shunt_ohm, args.max_current)

    c_gain, c_off = compute_two_point_calibration(
        args.curr_meas1, args.curr_ref1, args.curr_meas2, args.curr_ref2
    )
    v_gain, v_off = compute_two_point_calibration(
        args.vbus_meas1, args.vbus_ref1, args.vbus_meas2, args.vbus_ref2
    )
    t_gain, t_off = compute_two_point_calibration(
        args.tap_meas1, args.tap_ref1, args.tap_meas2, args.tap_ref2
    )

    commands = [
        f"SET_PACK {args.series_cells} {args.capacity_mah:.1f} {args.shunt_mohm:.4f}",
        f"SET_TAP_CAL {args.tap_channel} {t_gain:.6f} {t_off:.6f}",
        "SAVE",
    ]

    return {
        "ina226_registers": ina_math,
        "current_calibration": {"gain": round(c_gain, 6), "offset_a": round(c_off, 6)},
        "vbus_calibration": {"gain": round(v_gain, 6), "offset_v": round(v_off, 6)},
        "tap_calibration": {
            "channel": args.tap_channel,
            "nominal_divider_ratio": DEFAULT_DIVIDER_RATIOS[args.tap_channel - 1],
            "gain": round(t_gain, 6),
            "offset_v": round(t_off, 6),
        },
        "nvs_cli_commands": commands,
    }


def push_to_serial(port: str, baud: int, commands: list[str]) -> None:
    import serial  # type: ignore

    with serial.Serial(port, baudrate=baud, timeout=1.5) as ser:
        for cmd in commands:
            ser.write((cmd + "\n").encode("ascii"))
            resp = ser.readline().decode("utf-8", errors="replace").strip()
            print(f"[SERIAL TX] {cmd} -> {resp}")


def push_to_api(api_url: str, args: argparse.Namespace, result: Dict[str, Any]) -> None:
    import httpx

    tap_gains = [1.0] * 6
    tap_offsets = [0.0] * 6
    tap_gains[args.tap_channel - 1] = result["tap_calibration"]["gain"]
    tap_offsets[args.tap_channel - 1] = result["tap_calibration"]["offset_v"]

    payload = {
        "series_cells": args.series_cells,
        "nominal_capacity_mah": args.capacity_mah,
        "r_shunt_mohm": args.shunt_mohm,
        "max_expected_current_a": args.max_current,
        "current_gain": result["current_calibration"]["gain"],
        "current_offset_a": result["current_calibration"]["offset_a"],
        "vbus_gain": result["vbus_calibration"]["gain"],
        "vbus_offset_v": result["vbus_calibration"]["offset_v"],
        "tap_gains": tap_gains,
        "tap_offsets_v": tap_offsets,
    }
    resp = httpx.put(f"{api_url.rstrip('/')}/api/calibration", json=payload, timeout=5.0)
    resp.raise_for_status()
    print(f"[API UPDATED] {resp.json()}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="CellGuard 2-Point Shunt & Voltage Divider Calibration Utility"
    )
    p.add_argument("--series-cells", type=int, default=4, choices=range(1, 7))
    p.add_argument("--capacity-mah", type=float, default=5000.0)
    p.add_argument("--shunt-mohm", type=float, default=1.0)
    p.add_argument("--max-current", type=float, default=60.0)

    p.add_argument("--curr-meas1", type=float, default=0.0)
    p.add_argument("--curr-ref1", type=float, default=0.0)
    p.add_argument("--curr-meas2", type=float, default=10.0)
    p.add_argument("--curr-ref2", type=float, default=10.0)

    p.add_argument("--vbus-meas1", type=float, default=12.0)
    p.add_argument("--vbus-ref1", type=float, default=12.0)
    p.add_argument("--vbus-meas2", type=float, default=16.8)
    p.add_argument("--vbus-ref2", type=float, default=16.8)

    p.add_argument("--tap-channel", type=int, default=1, choices=range(1, 7))
    p.add_argument("--tap-meas1", type=float, default=3.0)
    p.add_argument("--tap-ref1", type=float, default=3.0)
    p.add_argument("--tap-meas2", type=float, default=4.2)
    p.add_argument("--tap-ref2", type=float, default=4.2)

    p.add_argument("--serial-port", type=str, default=None, help="Optional ESP32 COM/tty port")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--api-url", type=str, default=None, help="Optional FastAPI URL e.g. http://127.0.0.1:8006")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_calibration_calc(args)
    except ValueError as exc:
        print(f"Calibration error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    if args.serial_port:
        push_to_serial(args.serial_port, args.baud, result["nvs_cli_commands"])
    if args.api_url:
        push_to_api(args.api_url, args, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
