"""Tests for the Suptronics X120x integration, run against a fake UPS."""

from __future__ import annotations

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.suptronics_ups_x120x.const import (
    CONF_SENSOR_DEVICE_CLASS,
    CONF_SENSOR_INVERT_LOGIC,
    DOMAIN,
    EVENT_SHUTDOWN,
    SHUTDOWN_CONFIRM_SECONDS,
    SHUTDOWN_STARTUP_GRACE_SECONDS,
)

LEGACY_OPTIONS = {CONF_SENSOR_DEVICE_CLASS: "problem", CONF_SENSOR_INVERT_LOGIC: True}


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    """Set the integration up the way an upgrade from 2.1 finds it."""
    hass.loop.add_reader = lambda fd, callback: None  # type: ignore[method-assign]
    hass.loop.remove_reader = lambda fd: None  # type: ignore[method-assign]
    entry = MockConfigEntry(
        domain=DOMAIN, title="Suptronics X120x", data={}, options=LEGACY_OPTIONS,
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _poll(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_legacy_entity_ids_survive(hass: HomeAssistant, fake_hardware) -> None:
    """The four entities of version 2.x keep their ids and their meaning."""
    await _setup(hass)

    battery = hass.states.get("sensor.ups_battery_level")
    assert battery is not None
    assert float(battery.state) == 80.0
    assert hass.states.get("sensor.ups_battery_voltage").state == "4.0"
    assert hass.states.get("switch.ups_charging_on_off").state == "on"

    # Legacy sensor: "problem" that is on while mains power is lost.
    power = hass.states.get("binary_sensor.ups_power")
    assert power.state == "off"
    assert power.attributes["device_class"] == "problem"

    registry = er.async_get(hass)
    assert registry.async_get("sensor.ups_battery_level").unique_id == "ups_battery_level"
    assert registry.async_get("binary_sensor.ups_power").unique_id == "ups_power_loss"
    assert registry.async_get("switch.ups_charging_on_off").unique_id == "ups_charging_on_off"


async def test_new_entities_and_roles(hass: HomeAssistant, fake_hardware) -> None:
    """Every entity carries its role, so the card can find it in any language."""
    await _setup(hass)
    roles = {
        state.attributes.get("ups_role")
        for state in hass.states.async_all()
        if state.entity_id.split(".")[0] in ("sensor", "binary_sensor", "switch", "number")
    }
    assert {
        "battery", "battery_voltage", "ups_status", "battery_state", "runtime_estimate",
        "time_on_battery", "last_power_loss", "power_outages", "shutdown_countdown",
        "ac_power", "battery_charging", "battery_low", "power_loss",
        "charging", "auto_shutdown",
        "charge_limit_min", "charge_limit_max", "shutdown_below", "shutdown_after_minutes",
    } <= roles


async def test_charge_window_hysteresis(hass: HomeAssistant, fake_hardware) -> None:
    """Charging stops at the upper limit and resumes only at the lower one."""
    entry = await _setup(hass)
    coordinator = entry.runtime_data

    await coordinator.async_set_charge_limit(minimum=60, maximum=80)
    await hass.async_block_till_done()

    fake_hardware.capacity = 80.0
    await _poll(hass, entry)
    assert fake_hardware.charging_allowed is False

    # Between the limits: stays off (latched).
    fake_hardware.capacity = 70.0
    await _poll(hass, entry)
    assert fake_hardware.charging_allowed is False

    # At the lower limit: resumes.
    fake_hardware.capacity = 60.0
    await _poll(hass, entry)
    assert fake_hardware.charging_allowed is True

    # Widening the window re-arms the latch at once.
    fake_hardware.capacity = 85.0
    await _poll(hass, entry)
    assert fake_hardware.charging_allowed is False
    await coordinator.async_set_charge_limit(maximum=95)
    await hass.async_block_till_done()
    assert fake_hardware.charging_allowed is True


async def test_charging_switch_is_master(hass: HomeAssistant, fake_hardware) -> None:
    """Switch off means off, whatever the window says, and it is re-applied."""
    entry = await _setup(hass)
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.ups_charging_on_off"}, blocking=True
    )
    await hass.async_block_till_done()
    assert fake_hardware.charging_allowed is False
    assert hass.states.get("switch.ups_charging_on_off").state == "off"

    # Simulate the board silently re-enabling charging: the next poll fixes it.
    fake_hardware.charging_allowed = True
    await _poll(hass, entry)
    assert fake_hardware.charging_allowed is False
    assert hass.states.get("binary_sensor.suptronics_x120x_charging").state == "off"


async def test_settings_survive_reload(hass: HomeAssistant, fake_hardware) -> None:
    """Limits and the charging switch are restored after a reload."""
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    await coordinator.async_set_charge_limit(minimum=50, maximum=70)
    await coordinator.async_set_charging_switch(False)
    await coordinator.async_set_shutdown(enabled=True, below=15, after_minutes=30)
    await hass.async_block_till_done()

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    restored = entry.runtime_data
    assert restored.charge_limit_min == 50
    assert restored.charge_limit_max == 70
    assert restored.charging_switch_on is False
    assert restored.shutdown_enabled is True
    assert restored.shutdown_below == 15
    assert restored.shutdown_after_minutes == 30
    assert fake_hardware.charging_allowed is False


async def test_power_loss_status_and_outage_count(hass: HomeAssistant, fake_hardware) -> None:
    """Losing mains flips the status, the legacy sensor and the counters."""
    entry = await _setup(hass)
    fake_hardware.ac_present = False
    fake_hardware.capacity = 50.0
    await _poll(hass, entry)

    assert hass.states.get("sensor.suptronics_x120x_status").state == "on_battery"
    assert hass.states.get("binary_sensor.ups_power").state == "on"
    assert hass.states.get("binary_sensor.suptronics_x120x_ac_power").state == "off"
    assert hass.states.get("sensor.suptronics_x120x_power_outages").state == "1"
    assert hass.states.get("sensor.suptronics_x120x_last_power_loss").state != "unknown"

    fake_hardware.capacity = 10.0
    await _poll(hass, entry)
    assert hass.states.get("sensor.suptronics_x120x_status").state == "low_battery"

    fake_hardware.ac_present = True
    await _poll(hass, entry)
    assert hass.states.get("sensor.suptronics_x120x_status").state == "charging"
    assert hass.states.get("sensor.suptronics_x120x_power_outages").state == "1"


async def test_runtime_estimate_learns_rate(hass: HomeAssistant, fake_hardware) -> None:
    """After a measured discharge the runtime is estimated, even back on mains."""
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    assert hass.states.get("sensor.suptronics_x120x_estimated_runtime").state == "unknown"

    fake_hardware.ac_present = False
    fake_hardware.capacity = 80.0
    await _poll(hass, entry)

    # Ten minutes later the pack is at 70%: 60% per hour.
    coordinator._on_battery_since -= 600
    fake_hardware.capacity = 70.0
    await _poll(hass, entry)
    runtime = float(hass.states.get("sensor.suptronics_x120x_estimated_runtime").state)
    assert 65 <= runtime <= 75  # 70% / 60%/h = 70 min

    fake_hardware.ac_present = True
    await _poll(hass, entry)
    assert coordinator.learned_rate is not None
    assert 55 <= coordinator.learned_rate <= 65
    assert hass.states.get("sensor.suptronics_x120x_estimated_runtime").state != "unknown"


async def test_shutdown_on_low_battery(hass: HomeAssistant, fake_hardware) -> None:
    """Armed, on battery and below the threshold for a minute: host shutdown."""
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    coordinator._started_at -= SHUTDOWN_STARTUP_GRACE_SECONDS + 1
    await coordinator.async_set_shutdown(enabled=True, below=20)
    await hass.async_block_till_done()

    events = []
    hass.bus.async_listen(EVENT_SHUTDOWN, lambda event: events.append(event))
    calls = []

    async def fake_host_shutdown(call):
        calls.append(call)

    hass.services.async_register("hassio", "host_shutdown", fake_host_shutdown)

    fake_hardware.ac_present = False
    fake_hardware.capacity = 15.0
    await _poll(hass, entry)
    assert hass.states.get("sensor.suptronics_x120x_status").state == "shutting_down"
    countdown = hass.states.get("sensor.suptronics_x120x_shutdown_countdown")
    assert 0 < float(countdown.state) <= SHUTDOWN_CONFIRM_SECONDS
    assert not calls

    # Mains back for one sample: cancelled.
    fake_hardware.ac_present = True
    await _poll(hass, entry)
    assert hass.states.get("sensor.suptronics_x120x_status").state == "charging"
    assert coordinator._shutdown_armed_at is None

    # Gone again, and a minute passes.
    fake_hardware.ac_present = False
    await _poll(hass, entry)
    coordinator._shutdown_armed_at -= SHUTDOWN_CONFIRM_SECONDS + 1
    await _poll(hass, entry)
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["reason"] == "battery_level"
    assert len(calls) == 1


async def test_shutdown_after_minutes_on_battery(hass: HomeAssistant, fake_hardware) -> None:
    """The time rule fires with a healthy battery once the minutes are up."""
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    coordinator._started_at -= SHUTDOWN_STARTUP_GRACE_SECONDS + 1
    await coordinator.async_set_shutdown(enabled=True, below=10, after_minutes=5)
    await hass.async_block_till_done()
    events = []
    hass.bus.async_listen(EVENT_SHUTDOWN, lambda event: events.append(event))

    fake_hardware.ac_present = False
    fake_hardware.capacity = 90.0
    await _poll(hass, entry)
    assert coordinator._shutdown_armed_at is None

    coordinator._on_battery_since -= 5 * 60
    await _poll(hass, entry)
    assert coordinator._shutdown_armed_at is not None
    coordinator._shutdown_armed_at -= SHUTDOWN_CONFIRM_SECONDS + 1
    await _poll(hass, entry)
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["reason"] == "time_on_battery"


async def test_options_flow_keeps_legacy_keys(hass: HomeAssistant, fake_hardware) -> None:
    """The options dialog opens and saves under the 2.x option keys."""
    entry = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "scan_interval": 15,
            "low_battery_threshold": 25,
            CONF_SENSOR_DEVICE_CLASS: "power",
            CONF_SENSOR_INVERT_LOGIC: False,
        },
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.options[CONF_SENSOR_DEVICE_CLASS] == "power"
    assert entry.options["scan_interval"] == 15
    power = hass.states.get("binary_sensor.ups_power")
    assert power.attributes["device_class"] == "power"
    assert power.state == "on"  # invert off: on while mains present


async def test_config_flow_checks_hardware(hass: HomeAssistant, fake_hardware) -> None:
    """A missing board is reported in the dialog, not as a dead entry."""
    with patch(
        "custom_components.suptronics_ups_x120x.config_flow.check_device",
        side_effect=OSError("no device"),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
