"""Constants shared across the Suptronics X120x integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "suptronics_ups_x120x"
VERSION: Final = "3.0.0"

MANUFACTURER: Final = "Suptronics"
MODEL: Final = "X120x (X1200/X1201/X1202)"
PRODUCT_URL: Final = "https://suptronics.com/Raspberrypi/Power_mgmt/x120x-v1.0_software.html"

# The device registry identifier. Kept from 2.1.0 so an upgrade re-uses the
# existing device instead of creating a second one.
DEVICE_ID: Final = "x120x"

# --- Legacy option keys -------------------------------------------------------
# These literal strings are the option keys created by version 2.0.0. They are
# kept verbatim so entries created by older versions load unchanged.
CONF_SENSOR_DEVICE_CLASS: Final = "Power sensor device class"
CONF_SENSOR_INVERT_LOGIC: Final = "Power sensor invert logic"
DEFAULT_SENSOR_DEVICE_CLASS: Final = "problem"
DEFAULT_SENSOR_INVERT_LOGIC: Final = True
POWER_SENSOR_DEVICE_CLASSES: Final = ["problem", "power"]

# --- Options added in 3.0 -----------------------------------------------------
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_LOW_BATTERY: Final = "low_battery_threshold"
DEFAULT_SCAN_INTERVAL: Final = 30
DEFAULT_LOW_BATTERY: Final = 20

# --- Hardware -----------------------------------------------------------------
I2C_BUS: Final = 1
I2C_DEVICE_ADDRESS: Final = 0x36
REG_VOLTAGE: Final = 0x02
REG_CAPACITY: Final = 0x04
REG_VERSION: Final = 0x08

# GPIO 6: power-loss detect, high while the adapter supplies power.
PIN_POWER_LOSS: Final = 6
# GPIO 16: charge control. Driven high the board stops charging, driven low it
# charges, the same as the vendor command "pinctrl set 16 op dh / dl".
PIN_CHARGING: Final = 16

# --- Charge window ------------------------------------------------------------
ATTR_CHARGE_LIMIT_MIN: Final = "charge_limit_min"
ATTR_CHARGE_LIMIT_MAX: Final = "charge_limit_max"
DEFAULT_CHARGE_LIMIT_MIN: Final = 95.0
DEFAULT_CHARGE_LIMIT_MAX: Final = 100.0
CHARGE_LIMIT_FLOOR: Final = 20.0
# Above this the pack is treated as full: "charging" turns off even on mains.
CHARGE_COMPLETE_CAPACITY: Final = 99.0

# --- Automatic shutdown -------------------------------------------------------
DEFAULT_SHUTDOWN_BELOW: Final = 10.0
SHUTDOWN_BELOW_MIN: Final = 5.0
SHUTDOWN_BELOW_MAX: Final = 90.0
# Shut down after this many minutes on battery, whatever the level. 0 = off.
DEFAULT_SHUTDOWN_AFTER_MINUTES: Final = 0
SHUTDOWN_AFTER_MINUTES_MAX: Final = 240
# The condition has to hold this long without a break before anything happens.
SHUTDOWN_CONFIRM_SECONDS: Final = 60
# Nothing is shut down this long after Home Assistant starts, so a Pi booted
# on a flat battery can still be reached to stop it.
SHUTDOWN_STARTUP_GRACE_SECONDS: Final = 180
ATTR_SHUTDOWN_BELOW: Final = "shutdown_below"
ATTR_SHUTDOWN_AFTER_MINUTES: Final = "shutdown_after_minutes"
EVENT_SHUTDOWN: Final = f"{DOMAIN}_shutdown"

SHUTDOWN_REASON_LEVEL: Final = "battery_level"
SHUTDOWN_REASON_TIME: Final = "time_on_battery"

# --- Runtime estimate ---------------------------------------------------------
# The discharge rate is only trusted once the pack has been on battery this
# long and has dropped this much; before that the estimate is "unknown".
RUNTIME_MIN_SECONDS: Final = 120
RUNTIME_MIN_DROP_PERCENT: Final = 0.5
# Never claim more than this many minutes; beyond it the figure is noise.
RUNTIME_MAX_MINUTES: Final = 24 * 60

# --- Derived battery state ----------------------------------------------------
BATTERY_STATE_FULL: Final = "full"
BATTERY_STATE_HIGH: Final = "high"
BATTERY_STATE_MEDIUM: Final = "medium"
BATTERY_STATE_LOW: Final = "low"
BATTERY_STATE_CRITICAL: Final = "critical"
BATTERY_STATES: Final = [
    BATTERY_STATE_FULL,
    BATTERY_STATE_HIGH,
    BATTERY_STATE_MEDIUM,
    BATTERY_STATE_LOW,
    BATTERY_STATE_CRITICAL,
]
BATTERY_LEVEL_FULL: Final = 95.0
BATTERY_LEVEL_HIGH: Final = 60.0
BATTERY_LEVEL_MEDIUM: Final = 30.0
BATTERY_LEVEL_LOW: Final = 10.0

# --- Overall UPS status -------------------------------------------------------
UPS_STATUS_ONLINE: Final = "online"
UPS_STATUS_CHARGING: Final = "charging"
UPS_STATUS_ON_BATTERY: Final = "on_battery"
UPS_STATUS_LOW_BATTERY: Final = "low_battery"
UPS_STATUS_SHUTTING_DOWN: Final = "shutting_down"
UPS_STATUSES: Final = [
    UPS_STATUS_ONLINE,
    UPS_STATUS_CHARGING,
    UPS_STATUS_ON_BATTERY,
    UPS_STATUS_LOW_BATTERY,
    UPS_STATUS_SHUTTING_DOWN,
]

# --- Persistent settings ------------------------------------------------------
STORAGE_KEY: Final = f"{DOMAIN}.settings"
STORAGE_VERSION: Final = 1

# --- Dashboard card -----------------------------------------------------------
URL_BASE: Final = "/suptronics_ups_x120x_static"
CARD_FILENAME: Final = "suptronics-ups-card.js"
DATA_FRONTEND_REGISTERED: Final = "frontend_registered"
