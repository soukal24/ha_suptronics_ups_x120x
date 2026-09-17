"""Sensors for the Suptronics X120x UPS."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricPotential, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BATTERY_STATES, UPS_STATUSES
from .coordinator import UpsConfigEntry, UpsCoordinator, UpsState
from .entity import UpsEntity


@dataclass(frozen=True, kw_only=True)
class UpsSensorDescription(SensorEntityDescription):
    """Describes a UPS sensor."""

    value_fn: Callable[[UpsState], float | int | str | datetime | None]
    legacy_unique_id: str | None = None
    legacy_entity_id: str | None = None


SENSORS: tuple[UpsSensorDescription, ...] = (
    # --- kept from 2.x, same unique_id and entity_id ---------------------------
    UpsSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda state: state.capacity,
        legacy_unique_id="ups_battery_level",
        legacy_entity_id="sensor.ups_battery_level",
    ),
    UpsSensorDescription(
        key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=lambda state: state.voltage,
        legacy_unique_id="ups_battery_voltage",
        legacy_entity_id="sensor.ups_battery_voltage",
    ),
    # --- new in 3.0 -------------------------------------------------------------
    UpsSensorDescription(
        key="ups_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(UPS_STATUSES),
        value_fn=lambda state: state.status,
    ),
    UpsSensorDescription(
        key="battery_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(BATTERY_STATES),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.battery_state,
    ),
    UpsSensorDescription(
        key="runtime_estimate",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda state: state.runtime_minutes,
    ),
    UpsSensorDescription(
        key="time_on_battery",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda state: (
            round(state.time_on_battery / 60, 1) if state.time_on_battery is not None else 0
        ),
    ),
    UpsSensorDescription(
        key="last_power_loss",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda state: state.last_power_loss,
    ),
    UpsSensorDescription(
        key="last_power_restored",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.last_power_restored,
    ),
    UpsSensorDescription(
        key="power_outages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.outage_count,
    ),
    UpsSensorDescription(
        key="shutdown_countdown",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.shutdown_seconds_left,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UpsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPS sensors."""
    coordinator = entry.runtime_data
    async_add_entities(UpsSensor(coordinator, description) for description in SENSORS)


class UpsSensor(UpsEntity, SensorEntity):
    """A value read from, or derived from, the UPS."""

    entity_description: UpsSensorDescription

    def __init__(self, coordinator: UpsCoordinator, description: UpsSensorDescription) -> None:
        super().__init__(
            coordinator,
            description.key,
            legacy_unique_id=description.legacy_unique_id,
            legacy_entity_id=description.legacy_entity_id,
        )
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | datetime | None:
        """Return the current reading."""
        return self.entity_description.value_fn(self.coordinator.data)
