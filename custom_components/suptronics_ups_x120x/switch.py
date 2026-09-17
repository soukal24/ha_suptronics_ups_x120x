"""Charge control and automatic shutdown switches for the Suptronics X120x UPS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_CHARGE_LIMIT_MAX,
    ATTR_CHARGE_LIMIT_MIN,
    ATTR_SHUTDOWN_AFTER_MINUTES,
    ATTR_SHUTDOWN_BELOW,
)
from .coordinator import UpsConfigEntry, UpsCoordinator
from .entity import UpsEntity

CHARGING_SWITCH = SwitchEntityDescription(
    key="charging",
    device_class=SwitchDeviceClass.SWITCH,
)

SHUTDOWN_SWITCH = SwitchEntityDescription(
    key="auto_shutdown",
    device_class=SwitchDeviceClass.SWITCH,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UpsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPS switches."""
    async_add_entities(
        [
            UpsChargingSwitch(entry.runtime_data),
            UpsShutdownSwitch(entry.runtime_data),
        ]
    )


class UpsChargingSwitch(UpsEntity, SwitchEntity):
    """Whether the pack is allowed to charge at all.

    Kept from 2.x with the same unique_id and entity_id. It is the outer
    gate: the charge window can still pause charging while this is on. The
    state is persisted by the coordinator and re-applied on every poll.
    """

    entity_description = CHARGING_SWITCH

    def __init__(self, coordinator: UpsCoordinator) -> None:
        super().__init__(
            coordinator,
            CHARGING_SWITCH.key,
            legacy_unique_id="ups_charging_on_off",
            legacy_entity_id="switch.ups_charging_on_off",
        )

    @property
    def is_on(self) -> bool:
        """Return whether charging is allowed."""
        return self.coordinator.charging_switch_on

    def _entity_attributes(self) -> dict[str, Any]:
        """Expose the charge window, so a dashboard can show it in one place."""
        return {
            ATTR_CHARGE_LIMIT_MIN: self.coordinator.effective_charge_limit_min,
            ATTR_CHARGE_LIMIT_MAX: self.coordinator.charge_limit_max,
            "charging_now": self.coordinator.data.is_charging,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Allow the pack to charge."""
        await self.coordinator.async_set_charging_switch(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging the pack."""
        await self.coordinator.async_set_charging_switch(False)


class UpsShutdownSwitch(UpsEntity, SwitchEntity):
    """Shut the Raspberry Pi down cleanly when the UPS runs on battery.

    Off until the user turns it on, and persisted across restarts. The rules
    are the two number entities: a battery level, and a time on battery.
    """

    entity_description = SHUTDOWN_SWITCH

    def __init__(self, coordinator: UpsCoordinator) -> None:
        super().__init__(coordinator, SHUTDOWN_SWITCH.key)

    @property
    def is_on(self) -> bool:
        """Return whether the automatic shutdown is armed."""
        return self.coordinator.shutdown_enabled

    def _entity_attributes(self) -> dict[str, Any]:
        """What it will do, and whether this install can do it at all."""
        return {
            ATTR_SHUTDOWN_BELOW: self.coordinator.shutdown_below,
            ATTR_SHUTDOWN_AFTER_MINUTES: self.coordinator.shutdown_after_minutes,
            "host_shutdown_available": self.coordinator.host_shutdown_available,
            "seconds_left": self.coordinator.shutdown_seconds_left,
            "reason": self.coordinator.data.shutdown_reason,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Arm the automatic shutdown."""
        await self.coordinator.async_set_shutdown(enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disarm it, cancelling any countdown in progress."""
        await self.coordinator.async_set_shutdown(enabled=False)
