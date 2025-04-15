import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .hub import SuptronicsHub

_LOGGER = logging.getLogger(__name__)

DOMAIN = "suptronics_ups_x120x"
PLATFORMS = ["sensor", "binary_sensor", "switch"]

async def async_setup(hass: HomeAssistant, config: dict):
    """We do not use YAML-based setup; everything is via config flow."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    This function is called when the integration is set up from the UI (via config flow).
    - We create and store an instance of SuptronicsHub in hass.data.
    - We forward setup to the sensor, binary_sensor, and switch platforms.
    """
    _LOGGER.info("Setting up Suptronics X120x (entry_id=%s)", entry.entry_id)

    # Create hub instance
    hub = SuptronicsHub()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "hub": hub
    }

    # Forward setup to the defined platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Called when the user removes or disables the integration.
    - Unload the sensor, binary_sensor, and switch platforms.
    - Remove the hub instance from hass.data.
    """
    _LOGGER.info("Unloading Suptronics X120x (entry_id=%s)", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
