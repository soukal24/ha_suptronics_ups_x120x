"""Diagnostics support for the Suptronics X120x UPS."""

from __future__ import annotations

from dataclasses import asdict
import glob
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import UpsConfigEntry
from .hardware import list_gpiochips


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: UpsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the config entry."""
    coordinator = entry.runtime_data
    state = asdict(coordinator.data) if coordinator.data else None
    if state:
        for key in ("last_power_loss", "last_power_restored"):
            if state[key] is not None:
                state[key] = state[key].isoformat()

    return {
        "entry": {"options": dict(entry.options)},
        "state": state,
        "settings": {
            "charging_switch_on": coordinator.charging_switch_on,
            "charge_limit_min": coordinator.effective_charge_limit_min,
            "charge_limit_max": coordinator.charge_limit_max,
            "shutdown_enabled": coordinator.shutdown_enabled,
            "shutdown_below": coordinator.shutdown_below,
            "shutdown_after_minutes": coordinator.shutdown_after_minutes,
            "learned_discharge_rate_percent_per_hour": coordinator.learned_rate,
            "host_shutdown_available": coordinator.host_shutdown_available,
        },
        "hardware": {
            "gpiochip": coordinator.hardware.chip_path,
            "fuel_gauge_version": coordinator.hardware.chip_version,
            "i2c_devices": sorted(glob.glob("/dev/i2c-*")),
            "gpiochips": await hass.async_add_executor_job(list_gpiochips),
        },
    }
