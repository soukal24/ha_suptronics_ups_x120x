"""Shared entity base for the Suptronics X120x UPS."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_ID, DOMAIN
from .coordinator import UpsCoordinator

# Attribute every entity carries, so the dashboard card can find each one by
# its role instead of guessing from device classes or entity ids.
ATTR_ROLE = "ups_role"


class UpsEntity(CoordinatorEntity[UpsCoordinator]):
    """Common device info, naming and availability for every UPS entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UpsCoordinator,
        key: str,
        *,
        legacy_unique_id: str | None = None,
        legacy_entity_id: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        # Entities that existed before 3.0 keep their unique_id and their
        # entity_id, so history and automations carry over untouched.
        self._attr_unique_id = legacy_unique_id or f"{DOMAIN}_{key}"
        if legacy_entity_id:
            self.entity_id = legacy_entity_id
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, DEVICE_ID)})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The role marker, merged with whatever the entity adds."""
        return {ATTR_ROLE: self._key, **self._entity_attributes()}

    def _entity_attributes(self) -> dict[str, Any]:
        """Attributes specific to one entity; overridden where needed."""
        return {}
