"""Blocking hardware layer for the Suptronics X120x UPS.

Two pieces of hardware are involved:

* a MAX17040-family fuel gauge on I2C, holding cell voltage and state of
  charge;
* two GPIO lines on the 40-pin header: power-loss detect (input) and charge
  control (output).

Every method here blocks and must run in an executor thread, never in the
event loop. The GPIO lines are held open for the whole life of the object:
the moment the charge line is released the kernel returns it to its default
and the board goes back to charging.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import glob
import logging

import gpiod
from gpiod.line import Bias, Clock, Direction, Drive, Edge, Value
import smbus2

from .const import (
    BATTERY_LEVEL_FULL,
    BATTERY_LEVEL_HIGH,
    BATTERY_LEVEL_LOW,
    BATTERY_LEVEL_MEDIUM,
    BATTERY_STATE_CRITICAL,
    BATTERY_STATE_FULL,
    BATTERY_STATE_HIGH,
    BATTERY_STATE_LOW,
    BATTERY_STATE_MEDIUM,
    CHARGE_COMPLETE_CAPACITY,
    I2C_BUS,
    I2C_DEVICE_ADDRESS,
    PIN_CHARGING,
    PIN_POWER_LOSS,
    REG_CAPACITY,
    REG_VERSION,
    REG_VOLTAGE,
)

_LOGGER = logging.getLogger(__name__)

# The Raspberry Pi 5 exposes the 40-pin header on the RP1 chip. Older kernels
# present it as /dev/gpiochip4, newer ones as /dev/gpiochip0, so the chip is
# looked up by its label. Older Pis are listed for completeness.
HEADER_CHIP_LABELS = (
    "pinctrl-rp1",
    "pinctrl-bcm2712",
    "pinctrl-bcm2711",
    "pinctrl-bcm2835",
)
FALLBACK_CHIP_PATH = "/dev/gpiochip0"


class UpsError(Exception):
    """Raised when the UPS cannot be read or configured."""


@dataclass(frozen=True, slots=True)
class UpsSample:
    """One reading of the UPS state."""

    voltage: float
    capacity: float
    ac_present: bool

    @property
    def battery_state(self) -> str:
        """Coarse battery level band, from the gauge's state of charge."""
        if self.capacity >= BATTERY_LEVEL_FULL:
            return BATTERY_STATE_FULL
        if self.capacity >= BATTERY_LEVEL_HIGH:
            return BATTERY_STATE_HIGH
        if self.capacity >= BATTERY_LEVEL_MEDIUM:
            return BATTERY_STATE_MEDIUM
        if self.capacity >= BATTERY_LEVEL_LOW:
            return BATTERY_STATE_LOW
        return BATTERY_STATE_CRITICAL


def find_gpiochip_path() -> str:
    """Return the path of the GPIO chip that drives the 40-pin header."""
    found: dict[str, str] = {}
    for path in sorted(glob.glob("/dev/gpiochip*")):
        try:
            if not gpiod.is_gpiochip_device(path):
                continue
            with gpiod.Chip(path) as chip:
                found[chip.get_info().label] = path
        except OSError:
            continue
    for label in HEADER_CHIP_LABELS:
        if label in found:
            _LOGGER.debug("Header chip %s found at %s", label, found[label])
            return found[label]
    _LOGGER.debug(
        "No known header chip label found, falling back to %s", FALLBACK_CHIP_PATH
    )
    return FALLBACK_CHIP_PATH


def list_gpiochips() -> dict[str, dict[str, object]]:
    """Every GPIO chip with its label and line count, for diagnostics."""
    chips: dict[str, dict[str, object]] = {}
    for path in sorted(glob.glob("/dev/gpiochip*")):
        try:
            with gpiod.Chip(path) as chip:
                info = chip.get_info()
                chips[path] = {"label": info.label, "lines": info.num_lines}
        except OSError as err:
            chips[path] = {"error": str(err)}
    return chips


def check_device() -> None:
    """One read of the gauge, for the config flow. Raises OSError."""
    with smbus2.SMBus(I2C_BUS) as bus:
        bus.read_word_data(I2C_DEVICE_ADDRESS, REG_CAPACITY)


def _swap16(value: int) -> int:
    """The gauge returns big-endian words over a little-endian SMBus read."""
    return ((value << 8) & 0xFF00) | (value >> 8)


def is_charging(sample: UpsSample, charging_allowed: bool) -> bool:
    """Whether the pack is being charged.

    The gauge exposes no current register, so this is inferred: the board
    only charges on mains, with charging permitted, and while the pack is
    not already full.
    """
    return (
        sample.ac_present
        and charging_allowed
        and sample.capacity < CHARGE_COMPLETE_CAPACITY
    )


class UpsHardware:
    """Owns the I2C bus handle and the GPIO line requests for the UPS."""

    def __init__(self) -> None:
        self._bus: smbus2.SMBus | None = None
        self._chip: gpiod.Chip | None = None
        self._pld_request: gpiod.LineRequest | None = None
        self._chg_request: gpiod.LineRequest | None = None
        self._charging_allowed = True
        self._chip_version: int | None = None
        self.chip_path: str | None = None

    # --- Lifecycle ------------------------------------------------------------

    def open(self, charging_allowed: bool = True) -> None:
        """Open the I2C bus and claim both GPIO lines. Blocking."""
        self._charging_allowed = charging_allowed
        try:
            self._bus = smbus2.SMBus(I2C_BUS)
        except OSError as err:
            raise UpsError(
                f"Cannot open I2C bus {I2C_BUS} (/dev/i2c-{I2C_BUS}): {err}. "
                "Is I2C enabled?"
            ) from err

        try:
            self.chip_path = find_gpiochip_path()
            self._chip = gpiod.Chip(self.chip_path)
            self._pld_request = self._chip.request_lines(
                consumer="suptronics_x120x_power",
                config={
                    PIN_POWER_LOSS: gpiod.LineSettings(
                        direction=Direction.INPUT,
                        bias=Bias.PULL_UP,
                        edge_detection=Edge.BOTH,
                        debounce_period=timedelta(milliseconds=50),
                        event_clock=Clock.REALTIME,
                    )
                },
            )
            self._chg_request = self._chip.request_lines(
                consumer="suptronics_x120x_charge",
                config={PIN_CHARGING: self._charge_settings(charging_allowed)},
            )
        except OSError as err:
            self.close()
            raise UpsError(
                f"Cannot claim GPIO lines {PIN_POWER_LOSS}/{PIN_CHARGING} on "
                f"{self.chip_path}: {err}. Is another process holding them?"
            ) from err

        try:
            self._chip_version = self.read_word(REG_VERSION)
        except OSError:
            # Purely cosmetic; not every gauge in the family has the register.
            self._chip_version = None

        _LOGGER.debug(
            "UPS opened: i2c-%d@0x%02x, %s, PLD=%d CHG=%d charging=%s",
            I2C_BUS,
            I2C_DEVICE_ADDRESS,
            self.chip_path,
            PIN_POWER_LOSS,
            PIN_CHARGING,
            charging_allowed,
        )

    def close(self) -> None:
        """Release the lines and the bus. Blocking."""
        for name in ("_chg_request", "_pld_request"):
            request = getattr(self, name)
            if request is not None:
                try:
                    request.release()
                except OSError:
                    pass
                setattr(self, name, None)
        if self._chip is not None:
            self._chip.close()
            self._chip = None
        if self._bus is not None:
            try:
                self._bus.close()
            except OSError:
                pass
            self._bus = None

    @property
    def is_open(self) -> bool:
        """Whether both the bus and the lines are held."""
        return self._bus is not None and self._chg_request is not None

    @property
    def chip_version(self) -> int | None:
        """Version word reported by the fuel gauge, if it has one."""
        return self._chip_version

    @property
    def event_fd(self) -> int:
        """File descriptor that becomes readable on a power-loss edge."""
        if self._pld_request is None:
            raise UpsError("device is not open")
        return self._pld_request.fd

    def drain_events(self) -> None:
        """Consume pending edge events so the descriptor goes quiet again."""
        if self._pld_request is None:
            return
        try:
            self._pld_request.read_edge_events()
        except OSError as err:
            _LOGGER.debug("Reading GPIO edge events failed: %s", err)

    # --- Reading --------------------------------------------------------------

    def read_word(self, register: int) -> int:
        """Read a big-endian word from the fuel gauge. Raises OSError."""
        if self._bus is None:
            raise UpsError("device is not open")
        return _swap16(self._bus.read_word_data(I2C_DEVICE_ADDRESS, register))

    def read(self) -> UpsSample:
        """Take one sample of voltage, capacity and mains state. Blocking."""
        if self._bus is None or self._pld_request is None:
            raise UpsError("device is not open")
        try:
            raw_voltage = self.read_word(REG_VOLTAGE)
            raw_capacity = self.read_word(REG_CAPACITY)
        except OSError as err:
            raise UpsError(
                f"No reply from the fuel gauge at 0x{I2C_DEVICE_ADDRESS:02x}: {err}"
            ) from err
        try:
            pld = self._pld_request.get_value(PIN_POWER_LOSS)
        except OSError as err:
            raise UpsError(f"Cannot read GPIO {PIN_POWER_LOSS}: {err}") from err

        # VCELL: 78.125 uV per LSB. SOC: 1/256 % per LSB.
        voltage = raw_voltage * 78.125 / 1_000_000
        capacity = min(100.0, max(0.0, raw_capacity / 256))
        return UpsSample(
            voltage=round(voltage, 3),
            capacity=round(capacity, 2),
            # The line is pulled high while the adapter is supplying power.
            ac_present=(pld == Value.ACTIVE),
        )

    # --- Charge control -------------------------------------------------------

    @property
    def charging_allowed(self) -> bool:
        """Whether charging is currently permitted (last value written)."""
        return self._charging_allowed

    @staticmethod
    def _charge_settings(allowed: bool) -> gpiod.LineSettings:
        # Driven high the board stops charging, driven low it charges.
        return gpiod.LineSettings(
            direction=Direction.OUTPUT,
            drive=Drive.PUSH_PULL,
            output_value=Value.INACTIVE if allowed else Value.ACTIVE,
        )

    def set_charging(self, allowed: bool) -> None:
        """Enable or disable battery charging. Blocking."""
        if self._chg_request is None:
            raise UpsError("device is not open")
        try:
            self._chg_request.set_value(
                PIN_CHARGING, Value.INACTIVE if allowed else Value.ACTIVE
            )
        except OSError as err:
            raise UpsError(f"Cannot drive GPIO {PIN_CHARGING}: {err}") from err
        self._charging_allowed = allowed
        _LOGGER.debug("Charging %s", "enabled" if allowed else "disabled")
