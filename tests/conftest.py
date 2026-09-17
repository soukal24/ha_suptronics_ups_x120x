"""Test fixtures: a fake UPS in place of the I2C bus and the GPIO lines.

The hardware libraries have no wheels off the Raspberry Pi, so they are
replaced by stubs before the integration is imported, and the hardware
class itself is swapped for an in-memory fake the tests can drive.
"""

from __future__ import annotations

from collections.abc import Generator
import sys
import types
from unittest.mock import patch

import pytest

# --- stub gpiod and smbus2 --------------------------------------------------


def _stub_hardware_libraries() -> None:
    if "gpiod" in sys.modules:
        return
    gpiod = types.ModuleType("gpiod")
    line = types.ModuleType("gpiod.line")
    for enum_name in ("Bias", "Clock", "Direction", "Drive", "Edge", "Value"):
        members = {
            m: object()
            for m in (
                "INPUT",
                "OUTPUT",
                "PULL_UP",
                "AS_IS",
                "PUSH_PULL",
                "BOTH",
                "REALTIME",
                "ACTIVE",
                "INACTIVE",
            )
        }
        setattr(line, enum_name, type(enum_name, (), members))
    gpiod.line = line
    gpiod.Chip = object
    gpiod.LineSettings = object
    gpiod.LineRequest = object
    gpiod.is_gpiochip_device = lambda path: False
    sys.modules["gpiod"] = gpiod
    sys.modules["gpiod.line"] = line

    smbus2 = types.ModuleType("smbus2")
    smbus2.SMBus = object
    sys.modules["smbus2"] = smbus2


_stub_hardware_libraries()

# On Windows every asyncio loop opens a socket pair for its self-pipe, which
# the test plugin's socket guard refuses. Only there, leave sockets enabled;
# on Linux (where the integration actually runs) the guard stays in place.
if sys.platform == "win32":
    import pytest_socket

    pytest_socket.disable_socket = lambda allow_unix_socket=False: None

from custom_components.suptronics_ups_x120x.hardware import UpsSample  # noqa: E402


class FakeHardware:
    """Behaves like UpsHardware, but the readings are whatever the test sets."""

    def __init__(self) -> None:
        self.capacity = 80.0
        self.voltage = 4.0
        self.ac_present = True
        self.charging_allowed = True
        self.is_open = False
        self.chip_version = 0x0012
        self.chip_path = "/dev/gpiochip0"
        self.set_calls: list[bool] = []

    def open(self, charging_allowed: bool = True) -> None:
        self.charging_allowed = charging_allowed
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    @property
    def event_fd(self) -> int:
        return 99

    def drain_events(self) -> None:
        pass

    def read(self) -> UpsSample:
        return UpsSample(
            voltage=self.voltage, capacity=self.capacity, ac_present=self.ac_present
        )

    def set_charging(self, allowed: bool) -> None:
        self.charging_allowed = allowed
        self.set_calls.append(allowed)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load integrations from custom_components/."""


@pytest.fixture
def fake_hardware() -> Generator[FakeHardware]:
    """Swap the real hardware for the fake, and skip the frontend/GPIO wiring."""
    hardware = FakeHardware()
    with (
        patch(
            "custom_components.suptronics_ups_x120x.coordinator.UpsHardware",
            return_value=hardware,
        ),
        patch(
            "custom_components.suptronics_ups_x120x._async_register_frontend",
        ),
        patch(
            "custom_components.suptronics_ups_x120x.coordinator.UpsCoordinator._handle_gpio_event"
        ),
    ):
        yield hardware
