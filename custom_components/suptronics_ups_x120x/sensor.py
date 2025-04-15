import logging
import smbus2

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import PERCENTAGE

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Default I2C address for Suptronics UPS
DEVICE_ADDRESS = 0x36
# I2C bus number, typically '1' on Raspberry Pi
bus = smbus2.SMBus(1)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """
    Sets up the sensor platform by creating two sensor entities:
    - BatteryLevelSensor
    - BatteryVoltageSensor
    """
    _LOGGER.debug("sensor => async_setup_entry")
    ents = [
        BatteryLevelSensor(),
        BatteryVoltageSensor()
    ]
    async_add_entities(ents, True)

class BatteryLevelSensor(SensorEntity):
    """
    Sensor entity that represents the UPS battery percentage.
    It reads raw data from I2C register 0x04 and converts it to a percentage.
    """
    _attr_name = "UPS Battery Level"
    _attr_unique_id = "ups_battery_level"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self):
        self._state = None

    @property
    def native_value(self):
        """Returns the current battery level percentage."""
        return self._state

    async def async_update(self):
        """
        Called by Home Assistant to update the sensor state. 
        Reads from the device using I2C and calculates the percentage.
        """
        try:
            raw = self._read_register(DEVICE_ADDRESS, 0x04)
            if raw is not None:
                self._state = round(raw / 256.0, 2)
            else:
                self._state = None
        except Exception as e:
            _LOGGER.error("Error reading battery level: %s", e)
            self._state = None

    def _read_register(self, address, register):
        """
        Reads a word (2 bytes) from the specified register via I2C, swaps bytes (endianness),
        and returns the integer value or None if an error occurs.
        """
        try:
            data = bus.read_word_data(address, register)
            swapped = ((data & 0xFF) << 8) | (data >> 8)
            return swapped
        except Exception as e:
            _LOGGER.error("I2C error reg=0x%02X: %s", register, e)
            return None

class BatteryVoltageSensor(SensorEntity):
    """
    Sensor entity for UPS battery voltage (in volts).
    Reads raw data from I2C register 0x02 and converts it to a voltage value.
    """
    _attr_name = "UPS Battery Voltage"
    _attr_unique_id = "ups_battery_voltage"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = "V"

    def __init__(self):
        self._state = None

    @property
    def native_value(self):
        """Returns the current battery voltage."""
        return self._state

    async def async_update(self):
        """
        Called by Home Assistant to update the sensor state.
        Reads from the device using I2C and calculates the battery voltage.
        """
        try:
            raw = self._read_register(DEVICE_ADDRESS, 0x02)
            if raw is not None:
                # The scaling factor 78.125 μV per bit (from hardware datasheet).
                self._state = round(raw * 78.125 / 1_000_000, 3)
            else:
                self._state = None
        except Exception as e:
            _LOGGER.error("Error reading battery voltage: %s", e)
            self._state = None

    def _read_register(self, address, register):
        """
        Reads a word from the specified register via I2C, swaps bytes, 
        and returns the integer value or None if an error occurs.
        """
        try:
            data = bus.read_word_data(address, register)
            swapped = ((data & 0xFF) << 8) | (data >> 8)
            return swapped
        except Exception as e:
            _LOGGER.error("I2C error reg=0x%02X: %s", register, e)
            return None
