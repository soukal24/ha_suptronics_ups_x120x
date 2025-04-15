import logging
import gpiod

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .config_flow import (
    CONF_SENSOR_DEVICE_CLASS,
    CONF_SENSOR_INVERT_LOGIC
)

_LOGGER = logging.getLogger(__name__)

# Physical pin number for detecting power loss (GPIO line).
PIN_POWER_LOSS = 6

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """
    Setup for the binary_sensor platform. Called automatically when the integration is loaded.
    """
    _LOGGER.debug("binary_sensor => async_setup_entry")
    data = hass.data[DOMAIN][entry.entry_id]
    hub = data["hub"]

    ent = UpsPowerLossBinarySensor(hub, entry)
    async_add_entities([ent])

class UpsPowerLossBinarySensor(BinarySensorEntity):
    """
    Represents the UPS Power Loss detection as a binary sensor entity.
    This sensor reads from GPIO line events to detect power loss.
    """
    _attr_name = "UPS Power"
    _attr_unique_id = "ups_power_loss"
    _attr_should_poll = False

    def __init__(self, hub, config_entry: ConfigEntry):
        """
        Store the hub for GPIO operations and the config entry for advanced settings.
        """
        self._hub = hub
        self._entry = config_entry
        self._line = None
        self._attr_is_on = False

    @property
    def device_class(self):
        """
        Returns the device_class for the sensor (e.g., 'problem' or 'power'),
        as configured in the Options Flow.
        """
        return self._entry.options.get(CONF_SENSOR_DEVICE_CLASS, "problem")

    async def async_added_to_hass(self):
        """
        Called when the entity is added to Home Assistant. We configure and start listening for GPIO events here.
        """
        await super().async_added_to_hass()

        # Read invert logic setting from options
        invert = self._entry.options.get(CONF_SENSOR_INVERT_LOGIC, False)

        # Request the GPIO line from the hub
        self._line, is_on = self._hub.add_sensor(
            port=PIN_POWER_LOSS,
            active_low=invert,
            bounce_ms=50
        )
        self._attr_is_on = is_on
        _LOGGER.debug("PowerLoss sensor pin=%d => initial is_on=%s invert=%s", PIN_POWER_LOSS, is_on, invert)

        # Add a reader to event loop to handle GPIO events
        self.hass.loop.add_reader(self._line.fd, self._handle_gpio_event)

    async def async_will_remove_from_hass(self):
        """
        Called when the entity is about to be removed. We release the GPIO line and stop reading events.
        """
        await super().async_will_remove_from_hass()
        if self._line:
            _LOGGER.debug("Removing fd=%d, releasing line for pin=%d", self._line.fd, PIN_POWER_LOSS)
            self.hass.loop.remove_reader(self._line.fd)
            self._line.release()
            self._line = None

    @callback
    def _handle_gpio_event(self):
        """
        Callback to handle GPIO edge events from gpiod. Updates the state based on edge type.
        """
        for event in self._line.read_edge_events():
            if event.event_type == gpiod.EdgeEvent.Type.RISING_EDGE:
                self._attr_is_on = True
            else:
                self._attr_is_on = False

        self.schedule_update_ha_state(False)
