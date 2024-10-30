"""The Suptronics UPS X120x integration."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import load_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = "suptronics_ups_x120x"

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Suptronics UPS X120x integration."""
    _LOGGER.info("Setting up Suptronics UPS X120x integration")
    
    # Load the sensor platform
    load_platform(hass, 'sensor', DOMAIN, {}, config)
    
    return True