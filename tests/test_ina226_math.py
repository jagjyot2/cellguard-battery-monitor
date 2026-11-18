"""Unit tests for TI INA226 calibration register math and register decoding."""

import math
import pytest

from backend.analytics import (
    compute_cal_register,
    compute_current_lsb,
    compute_effective_current_lsb,
    compute_ina226_calibration_params,
    compute_power_lsb,
    decode_ina226_registers,
    encode_ina226_alert_limit,
)


def test_ina226_calibration_register_nominal_1mohm_60a():
    i_lsb = compute_current_lsb(60.0)
    assert math.isclose(i_lsb, 60.0 / 32768.0, rel_tol=1e-9)

    cal = compute_cal_register(0.001, i_lsb)
    # 0.00512 / ((60/32768) * 0.001) = 2796.2026 -> floor = 2796
    assert cal == 2796

    eff_lsb = compute_effective_current_lsb(0.001, cal)
    assert math.isclose(eff_lsb, 0.00512 / (2796 * 0.001), rel_tol=1e-9)
    assert math.isclose(compute_power_lsb(eff_lsb), 25.0 * eff_lsb, rel_tol=1e-9)


def test_ina226_full_scale_shunt_limit_check():
    ok = compute_ina226_calibration_params(r_shunt_ohm=0.001, max_expected_current_a=60.0)
    assert ok["within_81_92mv_limit"] is True
    assert ok["cal_register_hex"] == "0x0AEC"

    over = compute_ina226_calibration_params(r_shunt_ohm=0.002, max_expected_current_a=60.0)
    assert over["full_scale_shunt_mv"] == pytest.approx(120.0)
    assert over["within_81_92mv_limit"] is False


def test_ina226_decode_signed_discharge_and_charge():
    eff_lsb = 0.002  # 2 mA/bit
    # 20.0 A discharge across 1 mOhm -> 20 mV shunt (20mV / 2.5uV = 8000 counts)
    # 16.0 V bus -> 16.0 / 0.00125 = 12800 counts
    # Current counts = 20.0 / 0.002 = 10000 counts
    decoded = decode_ina226_registers(
        raw_shunt_int16=8000,
        raw_bus_uint16=12800,
        raw_curr_int16=10000,
        current_lsb_a=eff_lsb,
    )
    assert decoded["shunt_voltage_mv"] == pytest.approx(20.0)
    assert decoded["bus_voltage_v"] == pytest.approx(16.0)
    assert decoded["current_a"] == pytest.approx(20.0)
    assert decoded["power_w"] == pytest.approx(320.0)

    # Negative charge current -5.0 A (-2500 counts, -5 mV shunt = -2000 counts)
    chg = decode_ina226_registers(
        raw_shunt_int16=-2000,
        raw_bus_uint16=13440,  # 16.8V
        raw_curr_int16=-2500,
        current_lsb_a=eff_lsb,
        current_gain=1.01,
        current_offset_a=0.05,
    )
    assert chg["shunt_voltage_mv"] == pytest.approx(-5.0)
    assert chg["bus_voltage_v"] == pytest.approx(16.8)
    assert chg["current_a"] == pytest.approx(-5.0 * 1.01 + 0.05)


def test_ina226_alert_limit_encoding():
    # 45A overcurrent on 1 mOhm shunt = 45 mV / 2.5 uV = 18000
    assert encode_ina226_alert_limit("SOL", 45.0, r_shunt_ohm=0.001) == 18000
    # 25.5V bus overvoltage / 1.25 mV = 20400
    assert encode_ina226_alert_limit("BOL", 25.5) == 20400
    # 10.8V bus undervoltage / 1.25 mV = 8640
    assert encode_ina226_alert_limit("BUL", 10.8) == 8640
    # 500W power limit / 0.05 W/bit = 10000
    assert encode_ina226_alert_limit("POL", 500.0, power_lsb_w=0.05) == 10000

    with pytest.raises(ValueError):
        encode_ina226_alert_limit("INVALID", 10.0)


def test_ina226_invalid_inputs_raise():
    with pytest.raises(ValueError):
        compute_current_lsb(0.0)
    with pytest.raises(ValueError):
        compute_cal_register(-0.001, 0.002)
    with pytest.raises(ValueError):
        decode_ina226_registers(40000, 100, 100, 0.002)
