from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
import smbus2
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "suptronics_ups_x120x"

# I2C configuration
DEVICE_ADDRESS = 0x36  # Typical address for MAX17048
bus = smbus2.SMBus(1)  # Using I2C bus 1

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Suptronics UPS X120x sensor entities."""
    # Add both battery charge and battery voltage sensors to Home Assistant
    async_add_entities([
        SuptronicsUPSChargeSensor(),
        SuptronicsUPSVoltageSensor()
    ], True)

class SuptronicsUPSChargeSensor(SensorEntity):
    """Representation of the UPS battery charge sensor."""

    def __init__(self):
        """Initialize the battery charge sensor."""
        self._state = None  # Current state of the battery charge (in percentage)
        self._name = "UPS Battery Level"  # Name of the sensor as it will appear in Home Assistant
        self._attr_device_class = SensorDeviceClass.BATTERY  # Classifies the sensor as a battery type
        self._attr_native_unit_of_measurement = "%"  # Unit of measurement is percentage
        self._unique_id = "ups_x120x_battery_charge"  # Unique ID for this sensor instance

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the current battery charge."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID for this sensor."""
        return self._unique_id

    async def async_update(self):
        """Fetch new state data for the sensor."""
        try:
            # Read the raw battery charge data from the I2C register
            charge_raw = self._read_register(DEVICE_ADDRESS, 0x04)
            if charge_raw is not None:
                # Convert the raw data to a percentage (0-100%) and round to 2 decimal places
                self._state = round(charge_raw / 256.0, 2)
        except Exception as e:
            # Log an error if the reading fails and set state to None
            _LOGGER.error("Error reading battery charge from I2C: %s", e)
            self._state = None

    def _read_register(self, address, register):
        """Read data from I2C device register."""
        try:
            # Read a word (2 bytes) of data from the specified register
            data = bus.read_word_data(address, register)
            # Swap the bytes (since data might be in little-endian format)
            data = ((data & 0xFF) << 8) | (data >> 8)
            return data
        except Exception as e:
            # Log an error if reading fails
            _LOGGER.error("Error reading from I2C register %s: %s", register, e)
            return None

class SuptronicsUPSVoltageSensor(SensorEntity):
    """Representation of the UPS battery voltage sensor."""

    def __init__(self):
        """Initialize the battery voltage sensor."""
        self._state = None  # Current state of the battery voltage (in volts)
        self._name = "UPS Battery Voltage"  # Name of the sensor as it will appear in Home Assistant
        self._attr_device_class = SensorDeviceClass.VOLTAGE  # Classifies the sensor as a voltage type
        self._attr_native_unit_of_measurement = "V"  # Unit of measurement is volts
        self._unique_id = "ups_x120x_battery_voltage"  # Unique ID for this sensor instance

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the current battery voltage."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID for this sensor."""
        return self._unique_id

    async def async_update(self):
        """Fetch new state data for the sensor."""
        try:
            # Read the raw battery voltage data from the I2C register
            voltage_raw = self._read_register(DEVICE_ADDRESS, 0x02)
            if voltage_raw is not None:
                # Convert the raw data to volts (using a scale factor) and round to 3 decimal places
                self._state = round(voltage_raw * 78.125 / 1000000, 3)
        except Exception as e:
            # Log an error if the reading fails and set state to None
            _LOGGER.error("Error reading battery voltage from I2C: %s", e)
            self._state = None

    def _read_register(self, address, register):
        """Read data from I2C device register."""
        try:
            # Read a word (2 bytes) of data from the specified register
            data = bus.read_word_data(address, register)
            # Swap the bytes (since data might be in little-endian format)
            data = ((data & 0xFF) << 8) | (data >> 8)
            return data
        except Exception as e:
            # Log an error if reading fails
            _LOGGER.error("Error reading from I2C register %s: %s", register, e)
            return None
