"""Config flow for the Suptronics X120x integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_LOW_BATTERY,
    CONF_SCAN_INTERVAL,
    CONF_SENSOR_DEVICE_CLASS,
    CONF_SENSOR_INVERT_LOGIC,
    DEFAULT_LOW_BATTERY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SENSOR_DEVICE_CLASS,
    DEFAULT_SENSOR_INVERT_LOGIC,
    DOMAIN,
    POWER_SENSOR_DEVICE_CLASSES,
)
from .hardware import check_device

_LOGGER = logging.getLogger(__name__)


class SuptronicsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the one UPS this Raspberry Pi can carry.

    There is nothing to ask: the board always sits on I2C bus 1 at 0x36 with
    GPIO 6 and 16. The flow only checks that the gauge answers, so a board
    that is missing or has I2C disabled is reported here and not as a config
    entry that never loads.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm, then verify the hardware is reachable."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            try:
                await self.hass.async_add_executor_job(check_device)
            except OSError as err:
                _LOGGER.warning("UPS not reachable over I2C: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Suptronics X120x",
                    data={},
                    options={
                        CONF_SENSOR_DEVICE_CLASS: DEFAULT_SENSOR_DEVICE_CLASS,
                        CONF_SENSOR_INVERT_LOGIC: DEFAULT_SENSOR_INVERT_LOGIC,
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_LOW_BATTERY: DEFAULT_LOW_BATTERY,
                    },
                )
        return self.async_show_form(step_id="user", errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> SuptronicsOptionsFlow:
        """Return the options flow."""
        return SuptronicsOptionsFlow()


class SuptronicsOptionsFlow(OptionsFlow):
    """Polling, thresholds and the behaviour of the legacy power sensor."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_LOW_BATTERY: int(user_input[CONF_LOW_BATTERY]),
                    CONF_SENSOR_DEVICE_CLASS: user_input[CONF_SENSOR_DEVICE_CLASS],
                    CONF_SENSOR_INVERT_LOGIC: bool(user_input[CONF_SENSOR_INVERT_LOGIC]),
                }
            )

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(min=5, max=3600, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(
                    CONF_LOW_BATTERY,
                    default=options.get(CONF_LOW_BATTERY, DEFAULT_LOW_BATTERY),
                ): NumberSelector(
                    NumberSelectorConfig(min=1, max=99, step=1, mode=NumberSelectorMode.SLIDER)
                ),
                vol.Required(
                    CONF_SENSOR_DEVICE_CLASS,
                    default=options.get(CONF_SENSOR_DEVICE_CLASS, DEFAULT_SENSOR_DEVICE_CLASS),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=POWER_SENSOR_DEVICE_CLASSES,
                        translation_key="power_sensor_device_class",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SENSOR_INVERT_LOGIC,
                    default=options.get(CONF_SENSOR_INVERT_LOGIC, DEFAULT_SENSOR_INVERT_LOGIC),
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
