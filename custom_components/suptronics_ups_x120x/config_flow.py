import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Keys for storing configuration options in config_entry.options:
CONF_SENSOR_DEVICE_CLASS = "Power sensor device class"
CONF_SENSOR_INVERT_LOGIC = "Power sensor invert logic"

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
    """
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """
        Called when the user first adds the integration (no prior configuration).
        We set default options and create an entry with no data payload.
        """
        if user_input is not None:
            # We only allow one instance (unique_id=DOMAIN).
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            # Provide default options
            return self.async_create_entry(
                title="Suptronics X120x",
                data={},  # no data needed
                options={
                    # Default device_class is 'problem'
                    CONF_SENSOR_DEVICE_CLASS: "problem",
                    # Default invert logic is True
                    CONF_SENSOR_INVERT_LOGIC: True
                }
            )

        # If no user_input yet, show an empty form
        return self.async_show_form(step_id="user")

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

            # Save new options
            return self.async_create_entry(
                title="",
                data={
                    CONF_SENSOR_DEVICE_CLASS: actual_device_class,
                    CONF_SENSOR_INVERT_LOGIC: user_invert
                }
            )

        # Determine current (stored) device_class
        current_internal = self._entry.options.get(CONF_SENSOR_DEVICE_CLASS, "problem")
        # Convert internal to user-friendly label
        current_label = DEVICE_CLASS_LABELS.get(current_internal, "Problem")

        current_invert = self._entry.options.get(CONF_SENSOR_INVERT_LOGIC, True)

        data_schema = vol.Schema({
            vol.Required(CONF_SENSOR_DEVICE_CLASS, default=current_label):
                vol.In(DEVICE_CLASS_LABELS.values()),
            vol.Required(CONF_SENSOR_INVERT_LOGIC, default=current_invert):
                cv.boolean
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)
