"""Binary sensors for the Suptronics X120x UPS."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_SENSOR_DEVICE_CLASS,
    CONF_SENSOR_INVERT_LOGIC,
    DEFAULT_SENSOR_DEVICE_CLASS,
    DEFAULT_SENSOR_INVERT_LOGIC,
)
from .coordinator import UpsConfigEntry, UpsCoordinator, UpsState
from .entity import UpsEntity


@dataclass(frozen=True, kw_only=True)
class UpsBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a UPS binary sensor."""

    value_fn: Callable[[UpsState, UpsCoordinator], bool]


BINARY_SENSORS: tuple[UpsBinarySensorDescription, ...] = (
    UpsBinarySensorDescription(
        key="ac_power",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda state, _: state.ac_present,
    ),
    UpsBinarySensorDescription(
        key="battery_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda state, _: state.is_charging,
    ),
    UpsBinarySensorDescription(
        key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
        value_fn=lambda state, coordinator: state.capacity < coordinator.low_battery_threshold,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UpsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPS binary sensors."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        UpsBinarySensor(coordinator, description) for description in BINARY_SENSORS
    ]
    entities.append(UpsPowerLossSensor(coordinator))
    async_add_entities(entities)


class UpsBinarySensor(UpsEntity, BinarySensorEntity):
    """A boolean state derived from the UPS."""

    entity_description: UpsBinarySensorDescription
    _entity_domain = "binary_sensor"

    def __init__(
        self, coordinator: UpsCoordinator, description: UpsBinarySensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the current state."""
        return self.entity_description.value_fn(self.coordinator.data, self.coordinator)


class UpsPowerLossSensor(UpsEntity, BinarySensorEntity):
    """The power-loss sensor of version 2.x, kept for existing automations.

    Its device class and polarity come from the options the user chose in
    2.x: by default it is a "problem" that is on while mains power is gone.
    With invert logic off it is on while mains power is present instead.
    """

    _entity_domain = "binary_sensor"

    def __init__(self, coordinator: UpsCoordinator) -> None:
        super().__init__(
            coordinator,
            "power_loss",
            legacy_unique_id="ups_power_loss",
            legacy_entity_id="binary_sensor.ups_power",
        )

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """The class chosen in the options, "problem" unless changed."""
        value = self.coordinator.config_entry.options.get(
            CONF_SENSOR_DEVICE_CLASS, DEFAULT_SENSOR_DEVICE_CLASS
        )
        try:
            return BinarySensorDeviceClass(value)
        except ValueError:
            return BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """On while mains power is lost (or present, with invert logic off)."""
        invert = self.coordinator.config_entry.options.get(
            CONF_SENSOR_INVERT_LOGIC, DEFAULT_SENSOR_INVERT_LOGIC
        )
        ac_present = self.coordinator.data.ac_present
        return (not ac_present) if invert else ac_present
