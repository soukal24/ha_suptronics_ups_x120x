"""The Suptronics X120x UPS integration."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    CARD_FILENAME,
    DATA_FRONTEND_REGISTERED,
    DEVICE_ID,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    PRODUCT_URL,
    URL_BASE,
    VERSION,
)
from .coordinator import UpsConfigEntry, UpsCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card as early as Home Assistant will let us.

    Entry setup waits for the hardware and is retried with a backoff when it
    is not ready; the card has no reason to wait for any of that.
    """
    await _async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: UpsConfigEntry) -> bool:
    """Set up the UPS from a config entry."""
    await _async_register_frontend(hass)

    coordinator = UpsCoordinator(hass, entry)
    await coordinator.async_load_settings()

    try:
        await coordinator.async_open()
    except Exception as err:
        await coordinator.async_close()
        raise ConfigEntryNotReady(f"UPS hardware not reachable: {err}") from err

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await coordinator.async_close()
        raise

    entry.runtime_data = coordinator
    _async_register_device(hass, entry, coordinator)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: UpsConfigEntry) -> bool:
    """Unload the entry and hand the GPIO lines back to the kernel."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_close()
    return unloaded


async def _async_options_updated(hass: HomeAssistant, entry: UpsConfigEntry) -> None:
    """Reload when the options change, so they take effect without a restart."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_device(
    hass: HomeAssistant, entry: UpsConfigEntry, coordinator: UpsCoordinator
) -> None:
    """Create (or refresh) the UPS in the device registry.

    The identifier is the one 2.1.0 used, so an upgrade keeps the same
    device page and every entity stays attached to it.
    """
    chip_version = coordinator.hardware.chip_version
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEVICE_ID)},
        manufacturer=MANUFACTURER,
        name="Suptronics X120x",
        model=MODEL,
        sw_version=VERSION,
        hw_version=(f"fuel gauge rev {chip_version:04x}" if chip_version else None),
        configuration_url=PRODUCT_URL,
    )
    # Stack the UPS under the host machine when Home Assistant knows about it:
    # the "host" device the Supervisor registers under its own config entry.
    host = None
    for hassio_entry in hass.config_entries.async_entries("hassio"):
        for candidate in dr.async_entries_for_config_entry(registry, hassio_entry.entry_id):
            if ("hassio", "host") in candidate.identifiers:
                host = candidate
                break
    if host is not None and device.via_device_id != host.id:
        registry.async_update_device(device.id, via_device_id=host.id)


# --- Dashboard card -------------------------------------------------------------
# The card is registered as a Lovelace resource, as if added by hand under
# Settings -> Dashboards -> Resources. Injecting it into the frontend page
# instead would leave clients with a cached page showing "Custom element
# doesn't exist"; resources are fetched fresh by every dashboard. Dashboards
# in YAML mode have no resource store, and only there is injection used.


async def _async_register_frontend(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(DATA_FRONTEND_REGISTERED):
        return

    card_url = f"{URL_BASE}/{CARD_FILENAME}"
    frontend_dir = Path(__file__).parent / "frontend"

    # The URL carries the version *and* a fingerprint of the file itself, so
    # any change to the card (an update, or a file copied in by hand) gives a
    # new URL and no browser keeps serving a cached copy of the old one.
    fingerprint = await hass.async_add_executor_job(
        _card_fingerprint, frontend_dir / CARD_FILENAME
    )
    if fingerprint is None:
        _LOGGER.error(
            "Dashboard card not found at %s; the integration works, but the card "
            "will not appear. Reinstall the integration folder including frontend/",
            frontend_dir / CARD_FILENAME,
        )
        return

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(URL_BASE, str(frontend_dir), cache_headers=True)]
        )
    except (RuntimeError, ValueError) as err:
        _LOGGER.warning(
            "Could not register the static path for the UPS card at %s: %s. "
            "If %s does not load, add it manually as a dashboard resource",
            URL_BASE,
            err,
            card_url,
        )

    versioned_url = f"{card_url}?v={VERSION}-{fingerprint}"
    if await _async_ensure_lovelace_resource(hass, card_url, versioned_url):
        _LOGGER.info("UPS dashboard card registered as a Lovelace resource: %s", versioned_url)
    else:
        add_extra_js_url(hass, versioned_url)
        _LOGGER.info("Dashboards are in YAML mode; UPS card injected: %s", versioned_url)
    domain_data[DATA_FRONTEND_REGISTERED] = True


def _card_fingerprint(path: Path) -> str | None:
    """Short hash of the card file, or None when it is missing. Blocking."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:10]
    except OSError:
        return None


def _lovelace_resources(hass: HomeAssistant) -> Any | None:
    """The Lovelace resource store, or None when there is none to write to."""
    data = hass.data.get("lovelace")
    if data is None:
        return None
    resources = data.get("resources") if isinstance(data, dict) else getattr(data, "resources", None)
    if resources is None or not hasattr(resources, "async_create_item"):
        return None
    return resources


def _is_our_resource(item: dict[str, Any], card_url: str) -> bool:
    return str(item.get("url", "")).split("?", 1)[0] == card_url


async def _async_ensure_lovelace_resource(
    hass: HomeAssistant, card_url: str, versioned_url: str
) -> bool:
    """Create, update or de-duplicate our resource. False means "cannot"."""
    resources = _lovelace_resources(hass)
    if resources is None:
        return False
    try:
        await resources.async_get_info()
        ours = [item for item in resources.async_items() if _is_our_resource(item, card_url)]
        if not ours:
            await resources.async_create_item({"res_type": "module", "url": versioned_url})
            return True
        first, *duplicates = ours
        if first.get("url") != versioned_url or first.get("type") != "module":
            await resources.async_update_item(
                first["id"], {"res_type": "module", "url": versioned_url}
            )
        for item in duplicates:
            await resources.async_delete_item(item["id"])
    except Exception:  # noqa: BLE001 - any failure here must fall back, not break setup
        _LOGGER.warning(
            "Could not register the UPS card as a Lovelace resource; injecting it instead",
            exc_info=True,
        )
        return False
    return True


async def async_remove_entry(hass: HomeAssistant, entry: UpsConfigEntry) -> None:
    """Take the card's resource away together with the integration."""
    resources = _lovelace_resources(hass)
    if resources is None:
        return
    card_url = f"{URL_BASE}/{CARD_FILENAME}"
    try:
        await resources.async_get_info()
        for item in list(resources.async_items()):
            if _is_our_resource(item, card_url):
                await resources.async_delete_item(item["id"])
    except Exception:  # noqa: BLE001 - removal must not fail over a leftover
        _LOGGER.warning(
            "Could not remove the UPS card resource; delete it under "
            "Settings -> Dashboards -> Resources",
            exc_info=True,
        )
