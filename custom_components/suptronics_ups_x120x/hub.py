"""Hardware access (GPIO + I2C) for the Suptronics X120x integration.

All methods of SuptronicsHub perform blocking I/O and must be called
through hass.async_add_executor_job so they never run inside the
Home Assistant event loop.
"""
import glob
import logging
from datetime import timedelta

import gpiod
import smbus2
from gpiod.line import Direction, Value, Bias, Drive, Edge, Clock

from .const import I2C_BUS, I2C_DEVICE_ADDRESS, REG_CAPACITY

_LOGGER = logging.getLogger(__name__)

# The Raspberry Pi 5 exposes the 40-pin header GPIOs on the RP1 chip.
# Older Pi 5 kernels present it as /dev/gpiochip4, newer ones as
# /dev/gpiochip0, so we look the chip up by its label instead of relying
# on a hard-coded path.
RPI5_CHIP_LABEL = "pinctrl-rp1"
FALLBACK_CHIP_PATH = "/dev/gpiochip0"


def find_gpiochip_path() -> str:
    """Return the path of the GPIO chip that drives the 40-pin header."""
    for path in sorted(glob.glob("/dev/gpiochip*")):
        try:
            if not gpiod.is_gpiochip_device(path):
                continue
            with gpiod.Chip(path) as chip:
                if chip.get_info().label == RPI5_CHIP_LABEL:
                    _LOGGER.debug("Found %s at %s", RPI5_CHIP_LABEL, path)
                    return path
        except OSError:
            continue
    _LOGGER.debug(
        "No chip labelled %s found, falling back to %s",
        RPI5_CHIP_LABEL,
        FALLBACK_CHIP_PATH,
    )
    return FALLBACK_CHIP_PATH


def check_device() -> None:
    """Try to read from the UPS fuel gauge; raises OSError when unreachable.

    Used by the config flow to give the user a clear error message instead
    of creating a config entry that can never load.
    """
    with smbus2.SMBus(I2C_BUS) as bus:
        bus.read_word_data(I2C_DEVICE_ADDRESS, REG_CAPACITY)


class SuptronicsHub:
    """
    Helper class that owns the GPIO chip and the I2C bus and provides
    methods to request lines for sensors/switches and read UPS registers.
    """

    def __init__(self):
        path = find_gpiochip_path()
        _LOGGER.debug("SuptronicsHub init: opening %s and I2C bus %d", path, I2C_BUS)
        self._chip = gpiod.Chip(path)
        try:
            self._bus = smbus2.SMBus(I2C_BUS)
        except OSError:
            self._chip.close()
            raise

    def read_word(self, register) -> int:
        """
        Reads a word (2 bytes) from the specified fuel gauge register via I2C,
        swaps bytes (the chip returns big-endian words) and returns the value.
        Raises OSError on I2C communication problems.
        """
        data = self._bus.read_word_data(I2C_DEVICE_ADDRESS, register)
        return ((data & 0xFF) << 8) | (data >> 8)

    def close(self):
        """Releases the GPIO chip and the I2C bus."""
        _LOGGER.debug("SuptronicsHub close")
        self._chip.close()
        self._bus.close()

    def add_sensor(self, port, active_low, bounce_ms=50):
        """
        Requests a GPIO line for a sensor input (e.g., power loss).
        Sets up debouncing and edge detection.
        Returns (line_request, initial_is_on_state).
        """
        cfg = gpiod.LineSettings(
            direction=Direction.INPUT,
            active_low=active_low,
            bias=Bias.PULL_UP,
            edge_detection=Edge.BOTH,
            debounce_period=timedelta(milliseconds=bounce_ms),
            event_clock=Clock.REALTIME
        )
        line_request = self._chip.request_lines(
            consumer="suptronics_x120x_sensor",
            config={port: cfg}
        )
        val = line_request.get_value(port)
        is_on = (val == Value.ACTIVE)
        return line_request, is_on

    def add_switch(self, port, active_low, init_state):
        """
        Requests a GPIO line for a switch (output).
        We set the initial output state to ACTIVE or INACTIVE based on init_state.
        """
        cfg = gpiod.LineSettings(
            direction=Direction.OUTPUT,
            active_low=active_low,
            bias=Bias.AS_IS,
            drive=Drive.PUSH_PULL,
            output_value=Value.ACTIVE if init_state else Value.INACTIVE
        )
        line_request = self._chip.request_lines(
            consumer="suptronics_x120x_switch",
            config={port: cfg}
        )
        return line_request

    def turn_on(self, line_req, port):
        """
        Sets the specified GPIO line to ACTIVE, effectively turning the switch 'on'.
        """
        line_req.set_value(port, Value.ACTIVE)

    def turn_off(self, line_req, port):
        """
        Sets the specified GPIO line to INACTIVE, effectively turning the switch 'off'.
        """
        line_req.set_value(port, Value.INACTIVE)
