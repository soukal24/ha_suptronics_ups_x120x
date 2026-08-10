import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, REG_CAPACITY, REG_VOLTAGE, shared_device_info
from .hub import SuptronicsHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """
    Sets up the sensor platform by creating two sensor entities:
    - BatteryLevelSensor
    - BatteryVoltageSensor
    """
    _LOGGER.debug("sensor => async_setup_entry")
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    ents = [
        BatteryLevelSensor(hub),
        BatteryVoltageSensor(hub)
    ]
    async_add_entities(ents, True)


class UpsSensorBase(SensorEntity):
    """
    Common base for the UPS I2C sensors. Reads a register through the hub
    (in the executor, never blocking the event loop) and converts the raw
    word to the final value.
    """
    # MEASUREMENT enables long-term statistics for these sensors.
    _attr_state_class = SensorStateClass.MEASUREMENT
    _register: int

    def __init__(self, hub: SuptronicsHub):
        self._hub = hub
        self._attr_device_info = shared_device_info()

    async def async_update(self):
        """
        Called by Home Assistant to update the sensor state.
        Reads from the device using I2C in the executor.
        """
        try:
            raw = await self.hass.async_add_executor_job(
                self._hub.read_word, self._register
            )
        except OSError as e:
            # Log only on the transition to unavailable to avoid spamming.
            if self._attr_available:
                _LOGGER.error("I2C error reg=0x%02X: %s", self._register, e)
            self._attr_available = False
            return
        self._attr_available = True
        self._attr_native_value = self._convert(raw)

    def _convert(self, raw: int):
        raise NotImplementedError


class BatteryLevelSensor(UpsSensorBase):
    """
    Sensor entity that represents the UPS battery percentage.
    It reads raw data from I2C register 0x04 and converts it to a percentage.
    """
    _attr_name = "UPS Battery Level"
    _attr_unique_id = "ups_battery_level"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    # Show whole percent in the UI (the exact value stays in the state)
    _attr_suggested_display_precision = 0
    _register = REG_CAPACITY

    def __init__(self, hub: SuptronicsHub):
        super().__init__(hub)
        # Force the pre-2.1.0 entity_id so users' automations keep working
        # even on fresh installs where the device grouping would otherwise
        # generate a different id.
        self.entity_id = "sensor.ups_battery_level"

    def _convert(self, raw: int):
        return round(raw / 256.0, 2)


class BatteryVoltageSensor(UpsSensorBase):
    """
    Sensor entity for UPS battery voltage (in volts).
    Reads raw data from I2C register 0x02 and converts it to a voltage value.
    """
    _attr_name = "UPS Battery Voltage"
    _attr_unique_id = "ups_battery_voltage"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    # Show two decimals in the UI, e.g. 4.16 V
    _attr_suggested_display_precision = 2
    _register = REG_VOLTAGE

    def __init__(self, hub: SuptronicsHub):
        super().__init__(hub)
        # Force the pre-2.1.0 entity_id so users' automations keep working.
        self.entity_id = "sensor.ups_battery_voltage"

    def _convert(self, raw: int):
        # The scaling factor 78.125 uV per bit (from hardware datasheet).
        return round(raw * 78.125 / 1_000_000, 3)
