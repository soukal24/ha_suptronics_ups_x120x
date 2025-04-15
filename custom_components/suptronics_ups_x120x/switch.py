import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import STATE_ON

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Physical pin for controlling charging
PIN_CHARGING = 16
INVERT_LOGIC = True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """
    Setup for the switch platform. 
    Creates the UPS charging ON/OFF switch entity.
    """
    _LOGGER.debug("switch => async_setup_entry")
    data = hass.data[DOMAIN][entry.entry_id]
    hub = data["hub"]

    ent = UpsChargingSwitch(hub)
    async_add_entities([ent])

class UpsChargingSwitch(SwitchEntity, RestoreEntity):
    """
    Represents a switch to enable or disable UPS charging via GPIO.
    We restore the previous state on Home Assistant restart if available.
    """
    _attr_name = "UPS charging ON/OFF"
    _attr_unique_id = "ups_charging_on_off"
    _attr_should_poll = False

    def __init__(self, hub):
        self._hub = hub
        self._line = None
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """
        Called when the entity is added. We attempt to restore the last known state 
        (if any), then initialize the GPIO line with that state.
        """
        await super().async_added_to_hass()

        prev_state = await self.async_get_last_state()
        if prev_state and prev_state.state == STATE_ON:
            self._attr_is_on = True
        else:
            self._attr_is_on = False

        # Request the GPIO line from the hub
        self._line = self._hub.add_switch(
            port=PIN_CHARGING,
            active_low=True,  
            init_state=self._attr_is_on
        )
        _LOGGER.debug("Switch line request done for port=%d => is_on=%s", PIN_CHARGING, self._attr_is_on)

    async def async_will_remove_from_hass(self) -> None:
        """
        Called when the entity is about to be removed. We release the GPIO line.
        """
        await super().async_will_remove_from_hass()
        if self._line:
            _LOGGER.debug("Releasing line for port=%d", PIN_CHARGING)
            self._line.release()
            self._line = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """
        Turn on charging by setting the GPIO line to ACTIVE.
        """
        if not self._line:
            return
        self._hub.turn_on(self._line, PIN_CHARGING)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """
        Turn off charging by setting the GPIO line to INACTIVE.
        """
        if not self._line:
            return
        self._hub.turn_off(self._line, PIN_CHARGING)
        self._attr_is_on = False
        self.async_write_ha_state()
