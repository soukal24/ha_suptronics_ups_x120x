"""Constants shared across the Suptronics X120x integration."""
from homeassistant.helpers.device_registry import DeviceInfo

DOMAIN = "suptronics_ups_x120x"
PLATFORMS = ["sensor", "binary_sensor", "switch"]

# Keys for storing configuration options in config_entry.options.
# NOTE: these literal strings are kept for backwards compatibility with
# config entries created by version 2.0.0 - do not rename them.
CONF_SENSOR_DEVICE_CLASS = "Power sensor device class"
CONF_SENSOR_INVERT_LOGIC = "Power sensor invert logic"

DEFAULT_SENSOR_DEVICE_CLASS = "problem"
DEFAULT_SENSOR_INVERT_LOGIC = True

# I2C settings for the fuel gauge chip on the Suptronics board
I2C_BUS = 1
I2C_DEVICE_ADDRESS = 0x36
REG_VOLTAGE = 0x02
REG_CAPACITY = 0x04

# GPIO pins
PIN_POWER_LOSS = 6
PIN_CHARGING = 16


def shared_device_info() -> DeviceInfo:
    """Device registry entry shared by all entities.

    Giving every entity the same identifiers groups them under a single
    device card in the Home Assistant UI.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, "x120x")},
        name="Suptronics X120x",
        manufacturer="Suptronics",
        model="X120x (X1200/X1201/X1202)",
    )
