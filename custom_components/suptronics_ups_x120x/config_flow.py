import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_SENSOR_DEVICE_CLASS,
    CONF_SENSOR_INVERT_LOGIC,
    DEFAULT_SENSOR_DEVICE_CLASS,
    DEFAULT_SENSOR_INVERT_LOGIC,
    DOMAIN,
)
from .hub import check_device

_LOGGER = logging.getLogger(__name__)

# Maps the internal device classes to user-friendly labels
DEVICE_CLASS_LABELS = {
    "problem": "Problem",
    "power": "Power"
}
# Reverse map: user-friendly => internal
USER_FRIENDLY_TO_INTERNAL = {v: k for k, v in DEVICE_CLASS_LABELS.items()}


class SuptronicsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Config flow for Suptronics X120x:
    - Step for first-time user setup (async_step_user).
    - Creates a unique_id to avoid multiple instances.
    - Verifies the UPS is actually reachable over I2C before creating the entry.
    """
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """
        Called when the user first adds the integration (no prior configuration).
        We verify the hardware is reachable, then create an entry with default options.
        """
        errors = {}
        if user_input is not None:
            # We only allow one instance (unique_id=DOMAIN).
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            # Blocking I2C access runs in the executor.
            try:
                await self.hass.async_add_executor_job(check_device)
            except OSError as err:
                _LOGGER.warning("UPS not reachable over I2C: %s", err)
                errors["base"] = "cannot_connect"
            else:
                # Provide default options
                return self.async_create_entry(
                    title="Suptronics X120x",
                    data={},  # no data needed
                    options={
                        CONF_SENSOR_DEVICE_CLASS: DEFAULT_SENSOR_DEVICE_CLASS,
                        CONF_SENSOR_INVERT_LOGIC: DEFAULT_SENSOR_INVERT_LOGIC
                    }
                )

        # If no user_input yet (or the device was not found), show the form
        return self.async_show_form(step_id="user", errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """
        For later changes via the 'Options' button in the UI.
        Returns an instance of the options flow.
        """
        return SuptronicsOptionsFlowHandler(config_entry)


class SuptronicsOptionsFlowHandler(config_entries.OptionsFlow):
    """
    Flow to manage advanced settings such as device_class and invert_logic.
    """

    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        """
        Displays a form for changing the device_class and invert_logic.
        """
        if user_input is not None:
            # Convert user-friendly label to internal device_class
            chosen_label = user_input[CONF_SENSOR_DEVICE_CLASS]
            actual_device_class = USER_FRIENDLY_TO_INTERNAL[chosen_label]
            user_invert = user_input[CONF_SENSOR_INVERT_LOGIC]

            # Save new options (the integration reloads automatically via the
            # update listener registered in __init__.py)
            return self.async_create_entry(
                title="",
                data={
                    CONF_SENSOR_DEVICE_CLASS: actual_device_class,
                    CONF_SENSOR_INVERT_LOGIC: user_invert
                }
            )

        # Determine current (stored) device_class
        current_internal = self._entry.options.get(
            CONF_SENSOR_DEVICE_CLASS, DEFAULT_SENSOR_DEVICE_CLASS
        )
        # Convert internal to user-friendly label
        current_label = DEVICE_CLASS_LABELS.get(current_internal, "Problem")

        current_invert = self._entry.options.get(
            CONF_SENSOR_INVERT_LOGIC, DEFAULT_SENSOR_INVERT_LOGIC
        )

        data_schema = vol.Schema({
            vol.Required(CONF_SENSOR_DEVICE_CLASS, default=current_label):
                vol.In(DEVICE_CLASS_LABELS.values()),
            vol.Required(CONF_SENSOR_INVERT_LOGIC, default=current_invert):
                cv.boolean
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)
