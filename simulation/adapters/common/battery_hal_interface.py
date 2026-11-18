"""Simulator-Independent Battery HAL Interface for CellGuard (Python).

CRITICAL SAFETY INVARIANT:
CellGuard is strictly a NON-INVASIVE, READ-ONLY telemetry and health analytics
instrument operated alongside an external commercial BMS and inline main fuse.
This HAL interface exposes ZERO balancing, charging, or FET-switching methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class SafetyCapabilities:
    """Immutable safety boundary declaration enforced across all HAL adapters."""

    monitor_only: bool = True
    balancing_supported: bool = False
    charging_supported: bool = False
    fet_switching_supported: bool = False
    external_bms_required: bool = True
    inline_fuse_required: bool = True

    def validate(self) -> None:
        if not self.monitor_only:
            raise RuntimeError("Safety violation: monitor_only must be True.")
        if self.balancing_supported or self.charging_supported or self.fet_switching_supported:
            raise RuntimeError("Safety violation: actuation features are prohibited in CellGuard.")


@dataclass
class INA226Telemetry:
    """16-bit I2C shunt/bus monitor telemetry frame."""

    bus_voltage_v: float = 0.0
    shunt_voltage_mv: float = 0.0
    current_a: float = 0.0
    power_w: float = 0.0
    alert_active: bool = False
    valid: bool = True


@dataclass
class NTCTelemetry:
    """4-channel NTC thermistor array readings."""

    temperatures_c: List[float] = field(default_factory=lambda: [25.0, 25.0, 25.0, 25.0])
    resistances_ohm: List[float] = field(default_factory=lambda: [10000.0, 10000.0, 10000.0, 10000.0])
    sensor_faults: List[bool] = field(default_factory=lambda: [False, False, False, False])


@dataclass
class CellTapTelemetry:
    """Multiplexed 1S-6S cell tap ADC readings."""

    series_cells: int = 4
    tap_voltages_v: List[float] = field(default_factory=list)
    cell_voltages_v: List[float] = field(default_factory=list)
    mux_gnd_offset_mv: float = 0.0
    mux_vref_v: float = 2.048
    tap_fault: bool = False
    valid: bool = True


@dataclass
class AlarmOutputState:
    """Non-invasive hardware indicator & alert outputs (no pack actuation)."""

    led_alarm_red: bool = False   # GPIO17
    led_status_grn: bool = False  # GPIO18
    buzzer_alert: bool = False    # GPIO19
    cal_btn_pressed: bool = False # GPIO4


@dataclass
class HALTelemetryFrame:
    """Unified simulator-independent telemetry snapshot."""

    timestamp_s: float
    ina226: INA226Telemetry
    ntc: NTCTelemetry
    cell_taps: CellTapTelemetry
    alarms: AlarmOutputState


class BatteryHALInterface(ABC):
    """Canonical simulator-independent HAL for CellGuard backends (Wokwi, BenchTwin, HIL)."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return simulator/backend identifier (e.g. 'wokwi', 'benchtwin')."""

    def safety_capabilities(self) -> SafetyCapabilities:
        caps = SafetyCapabilities()
        caps.validate()
        return caps

    @abstractmethod
    def initialize(self, series_cells: int, r_shunt_ohm: float = 0.001, max_expected_a: float = 60.0) -> None:
        """Initialize pack configuration and shunt parameters."""

    @abstractmethod
    def read_ina226(self, timestamp_s: float) -> INA226Telemetry:
        """Read INA226 bus voltage, shunt voltage, current, power, and ALERT state."""

    @abstractmethod
    def read_ntc_channels(self, timestamp_s: float) -> NTCTelemetry:
        """Read 4 NTC temperature channels (GPIO39, GPIO34, GPIO35, GPIO32)."""

    @abstractmethod
    def read_cell_taps(self, timestamp_s: float) -> CellTapTelemetry:
        """Read multiplexed/divider cell tap voltages (B1..Bn) via GPIO36 + S0..S2."""

    @abstractmethod
    def write_alarm_outputs(self, outputs: AlarmOutputState) -> None:
        """Update non-invasive LED/buzzer indicators (GPIO17/18/19)."""

    def step_and_sample(self, timestamp_s: float, outputs: AlarmOutputState | None = None) -> HALTelemetryFrame:
        """Convenience helper to sample all telemetry channels and optionally update indicators."""
        if outputs is not None:
            self.write_alarm_outputs(outputs)
        return HALTelemetryFrame(
            timestamp_s=timestamp_s,
            ina226=self.read_ina226(timestamp_s),
            ntc=self.read_ntc_channels(timestamp_s),
            cell_taps=self.read_cell_taps(timestamp_s),
            alarms=outputs or AlarmOutputState(),
        )
