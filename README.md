# Suptronics UPS X120x for Home Assistant

Custom integration for the Suptronics / Geekworm **X120x** UPS boards
(X1200, X1201, X1202) on a Raspberry Pi 5 running Home Assistant.

Czech documentation: [README.cs.md](README.cs.md).

Version 3.0 is a complete rework: the integration now enforces charge limits
and shuts the Pi down on its own, estimates the remaining runtime, reacts to a
power loss the moment it happens, and ships an animated dashboard card. Every
entity from version 2 keeps its id, so existing automations and history carry
over.

## What it creates

One **device**, *Suptronics X120x*, with these entities:

| Entity | Type | Notes |
|---|---|---|
| Battery (`sensor.ups_battery_level`) | sensor | percent, from the fuel gauge |
| Battery voltage (`sensor.ups_battery_voltage`) | sensor | volts |
| Power loss (`binary_sensor.ups_power`) | binary sensor | the 2.x sensor: on while mains power is lost (configurable) |
| Battery charging (`switch.ups_charging_on_off`) | switch | master switch for charging |
| Status | sensor (enum) | `online`, `charging`, `on_battery`, `low_battery`, `shutting_down` |
| Battery level | sensor (enum) | full / high / medium / low / critical |
| AC power | binary sensor | mains present |
| Charging | binary sensor | the pack is actually being charged |
| Battery low | binary sensor | below the configurable threshold |
| Estimated runtime | sensor | minutes left on battery, learned from real outages |
| Time on battery | sensor | minutes since mains was lost |
| Last power loss / Last power restored | sensor | timestamps |
| Power outages | sensor | counter |
| Charge below / Charge up to | number | the charge window |
| Shutdown on low battery | switch | automatic clean shutdown, off by default |
| Shut down below | number | battery level for the shutdown |
| Shut down after minutes on battery | number | time rule for the shutdown, 0 = off |
| Shutdown countdown | sensor | seconds until the shutdown, while one is pending |

### The charge window

*Charge up to* and *Charge below* define a range with hysteresis, enforced by
the integration itself: charging stops at the upper limit and only resumes
once the level has fallen back to the lower one. Set them to 60 and 80 and
the pack stays in the band that slows its ageing, with no automation. The
defaults (95 to 100) match the board's own behaviour.

*Battery charging* is the master switch: with it off the pack never charges.
The setting is re-applied on every poll, so the board cannot drift back to
charging on its own, and it is persisted across restarts.

### Automatic shutdown

Turn *Shutdown on low battery* on and the Raspberry Pi is shut down cleanly
when the UPS is on battery and either rule fires:

- the battery is at or below *Shut down below*, or
- the UPS has been on battery for *Shut down after minutes on battery*.

Safety margins: mains power always wins and cancels a pending shutdown; the
condition has to hold for a full minute; nothing happens in the first three
minutes after Home Assistant starts; a persistent notification tells you how
to stop it. On Home Assistant OS and Supervised the shutdown uses
`hassio.host_shutdown`. On other install types the integration fires the
`suptronics_ups_x120x_shutdown` event instead, with `reason`, `capacity`,
`voltage` and `time_on_battery`, so an automation can do it.

For the Pi to power **back on** when mains returns, the Pi 5 must really power
off on halt. Set once in the EEPROM from Raspberry Pi OS:

```
sudo rpi-eeprom-config -e
POWER_OFF_ON_HALT=1
PSU_MAX_CURRENT=5000
```

### Runtime estimate

During an outage the integration measures how fast the pack drains and shows
the minutes left. The rate is remembered, so after the first real outage the
estimate is shown on mains too, as "what you would get if the power went
now". It stays *unknown* until an outage of at least two minutes has been
measured.

## The dashboard card

The integration serves its own card and registers it as a dashboard
resource by itself. Add it in the card picker as *Suptronics UPS*, or in YAML:

```yaml
type: custom:suptronics-ups-card
variant: full        # full | compact | gauge
hours: 24            # history window
name: Rack UPS       # optional title
language: cs         # optional, defaults to the Home Assistant language
```

It finds the entities on its own. The top bar shows the status (and the
countdown while a shutdown is pending), the dial shows the charge coloured
by band with the charge window as an outer arc, the tiles show the estimated
runtime, the time on battery or the last outage, the voltage and the outage
count. Below is the battery history with a mains strip (green on mains, red
during an outage), then the buttons for charging and automatic shutdown.
Every element opens the more-info dialog of its entity.

### Extra gauges

The values of the *System Monitor* integration (CPU temperature, CPU, memory
and disk use) can be added as mini dials with one line; the card finds the
entities on its own:

```yaml
type: custom:suptronics-ups-card
extras: system_monitor
```

Any other entity works too, with the same `severity` thresholds as the
built-in gauge card (ascending for a temperature, descending for a voltage):

```yaml
type: custom:suptronics-ups-card
extras:
  - entity: sensor.processor_temperature
    name: CPU °C
    min: 0
    max: 100
    severity: { green: 0, yellow: 65, red: 80 }
  - entity: sensor.memory_use_percent
    name: RAM
    severity: { green: 0, yellow: 75, red: 90 }
```

`unit` and `decimals` are optional overrides. Blocks can be forced on or off
with `show_stats`, `show_history`, `show_extras` and `show_actions`.

A complete example view, with badges, the card, classic gauges and the
System Monitor entities, is in [docs/dashboard-example.yaml](docs/dashboard-example.yaml).

If the card does not appear after an update, reload the browser page with
Ctrl+F5.

## Installation

### HACS

Add `https://github.com/soukal24/ha_suptronics_ups_x120x` as a custom
repository (category *Integration*), install *Suptronics X120x UPS* and
restart Home Assistant.

### Manual

Copy `custom_components/suptronics_ups_x120x/` into your `config/` directory
and restart.

### I2C

`/dev/i2c-1` has to exist. On Home Assistant OS add `dtparam=i2c_arm=on` to
`config.txt` on the boot partition (or use the HassOS I2C Configurator
add-on) and reboot.

### Setup

*Settings → Devices & services → Add integration → Suptronics X120x*. The
integration checks that the fuel gauge answers before creating the entry.

**Options** (Configure on the integration): polling interval, low battery
threshold, and the class and polarity of the legacy *Power loss* sensor.

## Upgrading from 2.x

Just update. The device and the four original entities keep their ids and
their history; the settings dialog keeps its two options. New entities
appear next to them. Any automation you had that toggled the charging switch
by battery level can be removed in favour of the charge window.

## Troubleshooting

- **"Could not reach the UPS" during setup**: I2C is not enabled, or the
  board is not seated on the header. `i2cdetect -y 1` should show `36`.
- **500 Internal Server Error when adding the integration** with
  `TypeError: 'NoneType' object is not subscriptable` in the log: corrupted
  `/config/deps`. Run `rm -rf /config/deps` from the Terminal add-on and
  restart Home Assistant.
- **Diagnostics**: the device page offers a diagnostics download with the
  current readings, all settings and the GPIO chips found.
- **Debug log**:

```yaml
logger:
  logs:
    custom_components.suptronics_ups_x120x: debug
```

## How it works

| What | Where | Detail |
|---|---|---|
| Cell voltage | I2C `0x36`, register `0x02` | 78.125 µV per LSB |
| State of charge | I2C `0x36`, register `0x04` | 1/256 % per LSB |
| Mains present | GPIO 6 | high while the adapter supplies power; edge events give instant detection |
| Charge control | GPIO 16 | driven high stops charging, low charges (the vendor's `pinctrl set 16 op dh/dl`) |

Both GPIO lines are held for the whole life of the integration. Releasing
the charge line returns the board to its default, which is charging.

## Credits and licence

MIT, see [LICENSE](LICENSE). Version 3.0 was reworked with the
[X120X integration by mesgas](https://github.com/mesgas/Suptronics-X120x-homeassistant)
as a reference; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Not affiliated with Suptronics or Geekworm.
