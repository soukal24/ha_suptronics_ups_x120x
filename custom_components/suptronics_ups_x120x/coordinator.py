"""Polling coordinator for the Suptronics X120x UPS.

The coordinator owns the hardware handles for the whole life of the config
entry, polls the fuel gauge, reacts at once to a power-loss edge on the GPIO
line, keeps the charge window, estimates the remaining runtime and decides
when the host has to be shut down.

Settings that used to live in automations (charge limits, shutdown rules)
are kept here and persisted in Home Assistant's storage, so they survive a
restart without every entity having to restore itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import time
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CHARGE_LIMIT_FLOOR,
    CONF_LOW_BATTERY,
    CONF_SCAN_INTERVAL,
    DEFAULT_CHARGE_LIMIT_MAX,
    DEFAULT_CHARGE_LIMIT_MIN,
    DEFAULT_LOW_BATTERY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SHUTDOWN_AFTER_MINUTES,
    DEFAULT_SHUTDOWN_BELOW,
    DOMAIN,
    EVENT_SHUTDOWN,
    RUNTIME_MAX_MINUTES,
    RUNTIME_MIN_DROP_PERCENT,
    RUNTIME_MIN_SECONDS,
    SHUTDOWN_AFTER_MINUTES_MAX,
    SHUTDOWN_BELOW_MAX,
    SHUTDOWN_BELOW_MIN,
    SHUTDOWN_CONFIRM_SECONDS,
    SHUTDOWN_REASON_LEVEL,
    SHUTDOWN_REASON_TIME,
    SHUTDOWN_STARTUP_GRACE_SECONDS,
    STORAGE_KEY,
    STORAGE_VERSION,
    UPS_STATUS_CHARGING,
    UPS_STATUS_LOW_BATTERY,
    UPS_STATUS_ON_BATTERY,
    UPS_STATUS_ONLINE,
    UPS_STATUS_SHUTTING_DOWN,
)
from .hardware import UpsError, UpsHardware, UpsSample, is_charging
from .texts import notification_text

_LOGGER = logging.getLogger(__name__)

type UpsConfigEntry = ConfigEntry[UpsCoordinator]

# How long a save of the settings is held back, to coalesce slider moves.
SAVE_DELAY_SECONDS = 2


@dataclass(frozen=True, slots=True)
class UpsState:
    """Everything the entities show, computed once per update."""

    voltage: float
    capacity: float
    ac_present: bool
    charging_allowed: bool
    is_charging: bool
    battery_state: str
    status: str
    time_on_battery: int | None
    runtime_minutes: int | None
    shutdown_seconds_left: int | None
    shutdown_reason: str | None
    last_power_loss: datetime | None
    last_power_restored: datetime | None
    outage_count: int


class UpsCoordinator(DataUpdateCoordinator[UpsState]):
    """Polls the UPS, owns the hardware and applies the charge and shutdown rules."""

    config_entry: UpsConfigEntry

    def __init__(self, hass: HomeAssistant, entry: UpsConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
            # A refresh asked for by a GPIO edge or a user action runs at once;
            # only a burst within one second is coalesced. The default cooldown
            # of ten seconds made the second of two quick changes wait.
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=1, immediate=True
            ),
        )
        self.hardware = UpsHardware()
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._reader_fd: int | None = None

        # --- persisted settings ------------------------------------------
        self.charging_switch_on = True
        self.charge_limit_min = DEFAULT_CHARGE_LIMIT_MIN
        self.charge_limit_max = DEFAULT_CHARGE_LIMIT_MAX
        self.shutdown_enabled = False
        self.shutdown_below = DEFAULT_SHUTDOWN_BELOW
        self.shutdown_after_minutes = DEFAULT_SHUTDOWN_AFTER_MINUTES
        # Learned discharge rate in percent per hour, from past outages.
        self.learned_rate: float | None = None
        self.outage_count = 0
        self.last_power_loss: datetime | None = None
        self.last_power_restored: datetime | None = None

        # --- runtime state -------------------------------------------------
        # Latched side of the charge window: True while the pack is below the
        # upper limit and has not yet been told to stop.
        self._window_allows = True
        self._started_at = time.monotonic()
        self._on_battery_since: float | None = None
        self._on_battery_start_capacity: float | None = None
        # An outage that was running when the previous run ended (a restart or
        # a reload during a power cut). The first sample continues it instead
        # of counting it again.
        self._resume_outage_from: datetime | None = None
        self._shutdown_armed_at: float | None = None
        self._shutdown_reason: str | None = None
        self._shutdown_requested = False
        self._last_sample: UpsSample | None = None

    # --- Derived settings -----------------------------------------------------

    @property
    def low_battery_threshold(self) -> int:
        """Capacity below which the battery is reported as low."""
        return self.config_entry.options.get(CONF_LOW_BATTERY, DEFAULT_LOW_BATTERY)

    @property
    def effective_charge_limit_min(self) -> float:
        """Lower limit, never above the upper one."""
        return min(self.charge_limit_min, self.charge_limit_max)

    @property
    def host_shutdown_available(self) -> bool:
        """Whether this installation can shut its own host down (HAOS/Supervised)."""
        return self.hass.services.has_service("hassio", "host_shutdown")

    @property
    def shutdown_seconds_left(self) -> int | None:
        """Seconds until the shutdown, while one is counting down."""
        if self._shutdown_armed_at is None or self._shutdown_requested:
            return None
        elapsed = time.monotonic() - self._shutdown_armed_at
        return max(0, round(SHUTDOWN_CONFIRM_SECONDS - elapsed))

    @property
    def time_on_battery(self) -> int | None:
        """Seconds since mains power was lost, None while on mains."""
        if self._on_battery_since is None:
            return None
        return int(time.monotonic() - self._on_battery_since)

    # --- Persistence ----------------------------------------------------------

    async def async_load_settings(self) -> None:
        """Restore the settings saved by a previous run."""
        stored = await self._store.async_load()
        if not stored:
            return
        self.charging_switch_on = bool(stored.get("charging_switch_on", True))
        self.charge_limit_min = float(stored.get("charge_limit_min", DEFAULT_CHARGE_LIMIT_MIN))
        self.charge_limit_max = float(stored.get("charge_limit_max", DEFAULT_CHARGE_LIMIT_MAX))
        self.shutdown_enabled = bool(stored.get("shutdown_enabled", False))
        self.shutdown_below = float(stored.get("shutdown_below", DEFAULT_SHUTDOWN_BELOW))
        self.shutdown_after_minutes = int(
            stored.get("shutdown_after_minutes", DEFAULT_SHUTDOWN_AFTER_MINUTES)
        )
        rate = stored.get("learned_rate")
        self.learned_rate = float(rate) if rate else None
        self.outage_count = int(stored.get("outage_count", 0))
        self.last_power_loss = _parse_datetime(stored.get("last_power_loss"))
        self.last_power_restored = _parse_datetime(stored.get("last_power_restored"))
        if stored.get("outage_active") and self.last_power_loss is not None:
            self._resume_outage_from = self.last_power_loss

    def _settings_to_save(self) -> dict[str, Any]:
        return {
            "charging_switch_on": self.charging_switch_on,
            "charge_limit_min": self.charge_limit_min,
            "charge_limit_max": self.charge_limit_max,
            "shutdown_enabled": self.shutdown_enabled,
            "shutdown_below": self.shutdown_below,
            "shutdown_after_minutes": self.shutdown_after_minutes,
            "learned_rate": self.learned_rate,
            "outage_count": self.outage_count,
            "last_power_loss": _format_datetime(self.last_power_loss),
            "last_power_restored": _format_datetime(self.last_power_restored),
            "outage_active": self._on_battery_since is not None,
        }

    @callback
    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._settings_to_save, SAVE_DELAY_SECONDS)

    # --- Lifecycle ------------------------------------------------------------

    async def async_open(self) -> None:
        """Claim the I2C bus and the GPIO lines and start listening for edges."""
        try:
            await self.hass.async_add_executor_job(
                self.hardware.open, self.charging_switch_on
            )
        except UpsError as err:
            raise UpdateFailed(str(err)) from err
        self._reader_fd = self.hardware.event_fd
        self.hass.loop.add_reader(self._reader_fd, self._handle_gpio_event)

    async def async_close(self) -> None:
        """Release the hardware. The board returns to its default: charging."""
        if self._reader_fd is not None:
            self.hass.loop.remove_reader(self._reader_fd)
            self._reader_fd = None
        await self.hass.async_add_executor_job(self.hardware.close)
        await self._store.async_save(self._settings_to_save())

    @callback
    def _handle_gpio_event(self) -> None:
        """A power-loss edge arrived: refresh now instead of at the next poll."""
        self.hardware.drain_events()
        self.hass.async_create_task(self.async_request_refresh())

    # --- Charge control -------------------------------------------------------

    async def async_set_charging_switch(self, allowed: bool) -> None:
        """Set the user's charge on/off intent."""
        self.charging_switch_on = allowed
        if allowed:
            # Re-arm the window so switching charging back on takes effect at
            # once instead of waiting for the pack to fall to the lower limit.
            self._window_allows = True
        self._schedule_save()
        await self.async_request_refresh()

    async def async_set_charge_limit(
        self, *, minimum: float | None = None, maximum: float | None = None
    ) -> None:
        """Move one end of the charge window."""
        if minimum is not None:
            self.charge_limit_min = max(CHARGE_LIMIT_FLOOR, min(100.0, minimum))
        if maximum is not None:
            self.charge_limit_max = max(CHARGE_LIMIT_FLOOR, min(100.0, maximum))
        # Re-arm the latch: widening the window must take effect without the
        # pack first draining to the lower limit. The next evaluation latches
        # it off again if the pack really is above the new upper limit.
        self._window_allows = True
        self._schedule_save()
        await self.async_request_refresh()

    def _charge_target(self, capacity: float) -> bool:
        """Decide whether charging should be enabled right now."""
        if capacity >= self.charge_limit_max:
            self._window_allows = False
        elif capacity <= self.effective_charge_limit_min:
            self._window_allows = True
        return self.charging_switch_on and self._window_allows

    # --- Automatic shutdown ---------------------------------------------------

    async def async_set_shutdown(
        self,
        *,
        enabled: bool | None = None,
        below: float | None = None,
        after_minutes: int | None = None,
    ) -> None:
        """Turn the automatic shutdown on or off, or change its rules."""
        if enabled is not None:
            self.shutdown_enabled = enabled
        if below is not None:
            self.shutdown_below = min(SHUTDOWN_BELOW_MAX, max(SHUTDOWN_BELOW_MIN, below))
        if after_minutes is not None:
            self.shutdown_after_minutes = int(
                min(SHUTDOWN_AFTER_MINUTES_MAX, max(0, after_minutes))
            )
        # Any change starts the confirmation over: raising a threshold while a
        # countdown runs must not turn into an instant shutdown.
        self._disarm_shutdown()
        self._schedule_save()
        await self.async_request_refresh()

    def _disarm_shutdown(self) -> None:
        if self._shutdown_armed_at is not None and not self._shutdown_requested:
            _LOGGER.info("Automatic shutdown cancelled")
        self._shutdown_armed_at = None
        self._shutdown_reason = None
        self._shutdown_requested = False
        persistent_notification.async_dismiss(self.hass, self._notification_id)

    @property
    def _notification_id(self) -> str:
        return f"{DOMAIN}_shutdown_{self.config_entry.entry_id}"

    def _text(self, key: str, **values: object) -> str:
        """A notification text in the language Home Assistant is set to."""
        return notification_text(self.hass.config.language, key, **values)

    def _shutdown_condition(self, sample: UpsSample) -> str | None:
        """Which rule, if any, says the host should go down right now."""
        if not self.shutdown_enabled or sample.ac_present:
            return None
        if sample.capacity <= self.shutdown_below:
            return SHUTDOWN_REASON_LEVEL
        on_battery = self.time_on_battery
        if (
            self.shutdown_after_minutes > 0
            and on_battery is not None
            and on_battery >= self.shutdown_after_minutes * 60
        ):
            return SHUTDOWN_REASON_TIME
        return None

    def _evaluate_shutdown(self, sample: UpsSample) -> None:
        """Decide, on every sample, whether it is time to shut the host down.

        The condition has to hold continuously for a full minute. Mains coming
        back at any point cancels it, and so does touching any setting.
        """
        reason = self._shutdown_condition(sample)
        if reason is None:
            if self._shutdown_armed_at is not None:
                self._disarm_shutdown()
            return

        now = time.monotonic()
        if now - self._started_at < SHUTDOWN_STARTUP_GRACE_SECONDS:
            return
        if self._shutdown_requested:
            return

        if self._shutdown_armed_at is None:
            self._shutdown_armed_at = now
            self._shutdown_reason = reason
            _LOGGER.warning(
                "On battery at %.0f%% (%s): shutting the host down in %s seconds "
                "unless mains power returns",
                sample.capacity,
                reason,
                SHUTDOWN_CONFIRM_SECONDS,
            )
            if reason == SHUTDOWN_REASON_TIME:
                message = self._text(
                    "shutdown_soon_time",
                    minutes=self.shutdown_after_minutes,
                    seconds=SHUTDOWN_CONFIRM_SECONDS,
                )
            else:
                message = self._text(
                    "shutdown_soon_level",
                    capacity=sample.capacity,
                    threshold=self.shutdown_below,
                    seconds=SHUTDOWN_CONFIRM_SECONDS,
                )
            persistent_notification.async_create(
                self.hass,
                message,
                title=self._text("shutdown_soon_title"),
                notification_id=self._notification_id,
            )
            return

        if now - self._shutdown_armed_at < SHUTDOWN_CONFIRM_SECONDS:
            return

        self._shutdown_requested = True
        self.hass.async_create_task(self._async_shutdown(sample, reason))

    async def _async_shutdown(self, sample: UpsSample, reason: str) -> None:
        """Announce the shutdown, then carry it out where that is possible."""
        # The event goes out first and always: on an install that cannot shut
        # its own host down, an automation listening for it is the only way
        # the machine gets switched off in time.
        self.hass.bus.async_fire(
            EVENT_SHUTDOWN,
            {
                "entry_id": self.config_entry.entry_id,
                "reason": reason,
                "capacity": sample.capacity,
                "voltage": sample.voltage,
                "threshold": self.shutdown_below,
                "after_minutes": self.shutdown_after_minutes,
                "time_on_battery": self.time_on_battery,
            },
        )
        # Make sure the outage statistics are on disk before the power goes.
        await self._store.async_save(self._settings_to_save())

        if not self.host_shutdown_available:
            _LOGGER.error(
                "Battery at %.0f%%: the host should be shut down now, but this "
                "installation has no hassio.host_shutdown action. The %s event "
                "has been fired for an automation to act on",
                sample.capacity,
                EVENT_SHUTDOWN,
            )
            persistent_notification.async_create(
                self.hass,
                self._text(
                    "shutdown_impossible",
                    capacity=sample.capacity,
                    event=EVENT_SHUTDOWN,
                ),
                title=self._text("shutdown_impossible_title"),
                notification_id=self._notification_id,
            )
            return

        _LOGGER.warning(
            "Battery at %.0f%% on battery power (%s): shutting the host down",
            sample.capacity,
            reason,
        )
        await self.hass.services.async_call("hassio", "host_shutdown", blocking=False)

    # --- Outage tracking and runtime estimate ---------------------------------

    def _track_outage(self, sample: UpsSample) -> None:
        """Notice power going and coming back; learn the discharge rate."""
        now = time.monotonic()
        resume_from = self._resume_outage_from
        self._resume_outage_from = None
        if not sample.ac_present and self._on_battery_since is None:
            if resume_from is not None:
                # Still the same power cut as before the restart: keep its
                # start time and do not count it twice. The discharge rate is
                # measured afresh from here.
                elapsed = max(0.0, (dt_util.utcnow() - resume_from).total_seconds())
                self._on_battery_since = now - elapsed
                self._on_battery_start_capacity = sample.capacity
                _LOGGER.info(
                    "Still on battery after restart, outage running for %d minutes",
                    elapsed // 60,
                )
                return
            self._on_battery_since = now
            self._on_battery_start_capacity = sample.capacity
            self.outage_count += 1
            self.last_power_loss = dt_util.utcnow()
            _LOGGER.warning("Mains power lost, battery at %.0f%%", sample.capacity)
            self._schedule_save()
        elif sample.ac_present and self._on_battery_since is not None:
            rate = self._current_rate(sample)
            if rate is not None:
                # Weighted towards the most recent outage: the load on the Pi
                # may have changed since the last one.
                self.learned_rate = (
                    rate if self.learned_rate is None else 0.5 * self.learned_rate + 0.5 * rate
                )
            self._on_battery_since = None
            self._on_battery_start_capacity = None
            self.last_power_restored = dt_util.utcnow()
            _LOGGER.info("Mains power restored, battery at %.0f%%", sample.capacity)
            self._schedule_save()

    def _current_rate(self, sample: UpsSample) -> float | None:
        """Discharge rate of the current outage in percent per hour, if known."""
        if self._on_battery_since is None or self._on_battery_start_capacity is None:
            return None
        elapsed = time.monotonic() - self._on_battery_since
        drop = self._on_battery_start_capacity - sample.capacity
        if elapsed < RUNTIME_MIN_SECONDS or drop < RUNTIME_MIN_DROP_PERCENT:
            return None
        return drop / elapsed * 3600

    def _runtime_minutes(self, sample: UpsSample) -> int | None:
        """Minutes until the pack is empty at the current or learned rate."""
        rate = self._current_rate(sample) or self.learned_rate
        if not rate or rate <= 0:
            return None
        minutes = sample.capacity / rate * 60
        return int(min(RUNTIME_MAX_MINUTES, max(0.0, minutes)))

    def _status(self, sample: UpsSample) -> str:
        if self._shutdown_armed_at is not None or self._shutdown_requested:
            return UPS_STATUS_SHUTTING_DOWN
        if not sample.ac_present:
            if sample.capacity < self.low_battery_threshold:
                return UPS_STATUS_LOW_BATTERY
            return UPS_STATUS_ON_BATTERY
        if is_charging(sample, self.hardware.charging_allowed):
            return UPS_STATUS_CHARGING
        return UPS_STATUS_ONLINE

    # --- Polling --------------------------------------------------------------

    async def _async_update_data(self) -> UpsState:
        try:
            sample = await self.hass.async_add_executor_job(self.hardware.read)
        except UpsError as err:
            raise UpdateFailed(str(err)) from err
        self._last_sample = sample

        self._track_outage(sample)

        target = self._charge_target(sample.capacity)
        if target != self.hardware.charging_allowed:
            _LOGGER.info(
                "Charge window: %s charging at %.1f%% (window %.0f-%.0f%%, switch %s)",
                "resuming" if target else "stopping",
                sample.capacity,
                self.effective_charge_limit_min,
                self.charge_limit_max,
                "on" if self.charging_switch_on else "off",
            )
            try:
                await self.hass.async_add_executor_job(self.hardware.set_charging, target)
            except UpsError as err:
                raise UpdateFailed(str(err)) from err

        self._evaluate_shutdown(sample)

        return UpsState(
            voltage=sample.voltage,
            capacity=sample.capacity,
            ac_present=sample.ac_present,
            charging_allowed=self.hardware.charging_allowed,
            is_charging=is_charging(sample, self.hardware.charging_allowed),
            battery_state=sample.battery_state,
            status=self._status(sample),
            time_on_battery=self.time_on_battery,
            runtime_minutes=self._runtime_minutes(sample),
            shutdown_seconds_left=self.shutdown_seconds_left,
            shutdown_reason=self._shutdown_reason,
            last_power_loss=self.last_power_loss,
            last_power_restored=self.last_power_restored,
            outage_count=self.outage_count,
        )


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    return dt_util.parse_datetime(str(value))


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
