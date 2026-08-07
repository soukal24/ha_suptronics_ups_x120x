import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .hub import SuptronicsHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    This function is called when the integration is set up from the UI (via config flow).
    - We create and store an instance of SuptronicsHub in hass.data.
    - We forward setup to the sensor, binary_sensor, and switch platforms.
    """
    _LOGGER.info("Setting up Suptronics X120x (entry_id=%s)", entry.entry_id)

    # Opening the GPIO chip and the I2C bus is blocking I/O, so it runs in
    # the executor. If the hardware is not reachable (yet), ConfigEntryNotReady
    # makes Home Assistant retry later instead of failing hard.
    try:
        hub = await hass.async_add_executor_job(SuptronicsHub)
    except OSError as err:
        raise ConfigEntryNotReady(f"UPS hardware not reachable: {err}") from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "hub": hub
    }

    # Reload the integration when the user changes options in the UI so the
    # new settings (e.g. invert logic) take effect without a restart.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Forward setup to the defined platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Called when the user saves the options flow."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Called when the user removes or disables the integration.
    - Unload the sensor, binary_sensor, and switch platforms.
    - Close the hub and remove it from hass.data.
    """
    _LOGGER.info("Unloading Suptronics X120x (entry_id=%s)", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(data["hub"].close)
    return unload_ok
