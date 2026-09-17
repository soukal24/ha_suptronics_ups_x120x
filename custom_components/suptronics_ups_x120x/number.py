"""Charge window and shutdown rules for the Suptronics X120x UPS."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CHARGE_LIMIT_FLOOR,
    SHUTDOWN_AFTER_MINUTES_MAX,
    SHUTDOWN_BELOW_MAX,
    SHUTDOWN_BELOW_MIN,
)
from .coordinator import UpsConfigEntry, UpsCoordinator
from .entity import UpsEntity


@dataclass(frozen=True, kw_only=True)
class UpsNumberDescription(NumberEntityDescription):
    """Describes a UPS setting, with how to read and write it."""

    get_fn: Callable[[UpsCoordinator], float]
    set_fn: Callable[[UpsCoordinator, float], Awaitable[None]]


NUMBERS: tuple[UpsNumberDescription, ...] = (
    UpsNumberDescription(
        key="charge_limit_min",
        entity_category=EntityCategory.CONFIG,
        native_min_value=CHARGE_LIMIT_FLOOR,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        get_fn=lambda c: c.charge_limit_min,
        set_fn=lambda c, v: c.async_set_charge_limit(minimum=v),
    ),
    UpsNumberDescription(
        key="charge_limit_max",
        entity_category=EntityCategory.CONFIG,
        native_min_value=CHARGE_LIMIT_FLOOR,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        get_fn=lambda c: c.charge_limit_max,
        set_fn=lambda c, v: c.async_set_charge_limit(maximum=v),
    ),
    UpsNumberDescription(
        key="shutdown_below",
        entity_category=EntityCategory.CONFIG,
        native_min_value=SHUTDOWN_BELOW_MIN,
        native_max_value=SHUTDOWN_BELOW_MAX,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        get_fn=lambda c: c.shutdown_below,
        set_fn=lambda c, v: c.async_set_shutdown(below=v),
    ),
    UpsNumberDescription(
        key="shutdown_after_minutes",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=SHUTDOWN_AFTER_MINUTES_MAX,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        get_fn=lambda c: c.shutdown_after_minutes,
        set_fn=lambda c, v: c.async_set_shutdown(after_minutes=int(v)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UpsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPS settings."""
    coordinator = entry.runtime_data
    async_add_entities(UpsNumber(coordinator, description) for description in NUMBERS)


class UpsNumber(UpsEntity, NumberEntity):
    """A setting kept by the coordinator and persisted across restarts."""

    entity_description: UpsNumberDescription

    def __init__(self, coordinator: UpsCoordinator, description: UpsNumberDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.entity_description.get_fn(self.coordinator)

    async def async_set_native_value(self, value: float) -> None:
        """Change the setting."""
        await self.entity_description.set_fn(self.coordinator, value)
        self.async_write_ha_state()
