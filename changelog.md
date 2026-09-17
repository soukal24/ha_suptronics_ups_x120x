# Changelog

All notable changes to this project will be documented in this file.  
Use it as both the changelog and the release notes for GitHub.

---

## [3.0.0] - unreleased

A complete rework. Every entity from 2.x keeps its `unique_id` and its
`entity_id`, the device keeps its identifier and the two options keep their
keys, so an update carries history, automations and settings over.

### Added
- **Charge window** (`number` *Charge below* / *Charge up to*) with
  hysteresis, enforced by the integration itself. Defaults 95-100 % match
  the board.
- **Automatic shutdown** (`switch` *Shutdown on low battery*, `number`
  *Shut down below* and *Shut down after minutes on battery*): clean host
  shutdown via `hassio.host_shutdown`, or the `suptronics_ups_x120x_shutdown`
  event on installs that cannot shut themselves down. One minute of
  confirmation, three minutes of grace after startup, mains always wins, a
  persistent notification while the countdown runs.
- **Estimated runtime** sensor, learned from the measured discharge rate of
  real outages and shown on mains as well once one has been measured.
- **Status** enum sensor (`online`, `charging`, `on_battery`, `low_battery`,
  `shutting_down`), **Battery level** band, **AC power**, **Charging** and
  **Battery low** binary sensors.
- **Time on battery**, **Last power loss**, **Last power restored**,
  **Power outages** and **Shutdown countdown** sensors.
- **Dashboard card** `custom:suptronics-ups-card` (full / compact / slim /
  gauge), served and registered as a Lovelace resource by the integration.
  Follows the Home Assistant language (English, Czech), `language:` overrides.
- **Instant power-loss detection**: the GPIO edge triggers a refresh at once
  instead of waiting for the next poll.
- **Diagnostics** download on the device page.
- Options: polling interval and low battery threshold.
- Czech translation of everything, including the shutdown notifications.
- Tests (`tests/`, pytest-homeassistant-custom-component).

### Changed
- One coordinator owns the hardware for the whole life of the entry. The
  charge pin is held open and its state re-applied on every poll, which fixes
  the switch "turning itself back on" reported on 2.x: previously the line was
  released on every reload and a failed pin request made the switch silently
  ignore commands.
- Settings (charge switch, limits, shutdown rules, learned discharge rate,
  outage counters) are persisted in `.storage`, not restored per entity.
- The legacy `binary_sensor.ups_power` keeps its options (device class,
  invert logic) and its meaning; the new `AC power` sensor is the plain one.
- Battery level and voltage are read by the coordinator instead of per
  entity.

### Credits
- Reworked with the X120X integration by mesgas (MIT) as a reference; see
  THIRD_PARTY_NOTICES.md.

---

## [2.1.1] - 2026-08-10

### Fixed
- **Entity IDs are stable again**: version 2.1.0 grouped all entities under a
  device, which caused Home Assistant to generate different entity IDs on
  fresh installs (breaking automations that reference the documented IDs).
  The original IDs (`sensor.ups_battery_level`, `sensor.ups_battery_voltage`,
  `binary_sensor.ups_power`, `switch.ups_charging_on_off`) are now enforced
  explicitly. Existing installs that only update are not affected.
  If you re-added the integration on 2.1.0 and got different IDs, remove the
  integration and add it again to get the original IDs back.

### Changed
- **Display precision**: battery voltage now shows two decimals by default
  (e.g. 4.16 V) and battery level shows whole percent (e.g. 98 %). The exact
  values are still recorded in history; you can override the precision per
  entity in its settings.

---

## [2.1.0] - 2026-08-07

No new features, no breaking changes — this release focuses on robustness,
better Home Assistant integration and a nicer UI. Existing entities keep
their IDs and history.

### Added
- **Long-term statistics**: battery level and voltage sensors now report
  `state_class: measurement`, so Home Assistant records long-term statistics.
- **Device grouping**: all entities are now grouped under a single
  "Suptronics X120x" device in the UI.
- **Hardware check during setup**: the config flow now verifies the UPS is
  reachable over I2C and shows a clear error message instead of failing with
  a cryptic error.
- **Translations**: config/options dialogs now have proper texts in English
  and Czech (`strings.json`, `translations/`).
- **`hacs.json`** for smoother HACS custom-repository installs.
- **Troubleshooting section** in the README (including the `/config/deps`
  fix for the "500 Internal Server Error" issue).

### Changed
- **No more blocking I/O in the event loop**: all I2C reads and GPIO
  operations now run in the executor, preventing "Detected blocking call"
  warnings and UI freezes when the hardware is slow.
- **Options apply immediately**: changing device class or invert logic in
  the options dialog reloads the integration automatically — no restart
  needed anymore.
- **Graceful startup**: if the hardware is not reachable at startup, the
  integration reports "not ready" and Home Assistant retries automatically.
- **Raspberry Pi 5 GPIO chip auto-detection**: the GPIO chip is found by its
  label (`pinctrl-rp1`), so the integration works on both older Pi 5 kernels
  (`gpiochip4`) and newer ones (`gpiochip0`).
- Sensors now report as **unavailable** (instead of unknown) when I2C reads
  fail, and errors are logged only once per outage instead of repeatedly.

### Fixed
- Inconsistent default for invert logic between initial setup and later
  reads (now consistently `true`).
- The I2C bus and GPIO chip are properly closed when the integration is
  unloaded.

---

## [2.0.0] - 2025-04-15

### Highlights
- **Full UI-based Configuration Flow**: No more YAML for setting up the integration.
- **New Entities**: Automatically creates battery sensors (level and voltage), a power-loss binary sensor, and a charging switch.
- **Improved Documentation**: Revised README with clearer instructions (installation, I2C enabling, usage).
- **English Code Comments**: The entire codebase now includes English comments for easier maintenance.

### Breaking Changes
- **Old YAML Configuration Must Be Removed**:
  - If you used:
    ```yaml
    suptronics_ups_x120x:
    ```
    remove those lines.  
  - If you manually configured the UPS using `rpi_gpio` sensors/switches like:
    ```yaml
    binary_sensor:
      - platform: rpi_gpio
        sensors:
          - port: 6
            name: "UPS Power loss"
            unique_id: "ups_power_loss_detect"
            invert_logic: true
            pull_mode: "UP"
    
    switch:
      - platform: rpi_gpio
        switches:
          - port: 16
            name: "UPS charging ON/OFF"
            unique_id: "ups_charging_switch"
            persistent: true
            invert_logic: true
    ```
    remove these as well. The new integration now handles these entities internally.

### Added
- **Binary Sensor** for detecting power loss.
- **Switch** for enabling or disabling UPS charging.
- **Options Flow** to easily change device class and invert logic from the UI.
- **Detailed I2C Setup Guide** and troubleshooting tips in `README.md`.

### Changed
- **Automatic Setup**: The integration now automatically creates and manages all sensors, binary sensor, and switch.  
- **Inverted Logic Support**: Configurable via the integration’s UI rather than YAML.

### Fixed
- **I2C Read Errors**: Corrected byte-swapping to ensure accurate battery level and voltage readings.
- **GPIO Cleanup**: Ensured proper release of GPIO lines when unloading the integration.

### Upgrade Steps
1. Remove any old YAML entries referencing `suptronics_ups_x120x`.
2. Remove any `rpi_gpio` configurations you used for UPS sensors or switches.
3. Update your files under `custom_components/suptronics_ups_x120x` with the new version.
4. Restart Home Assistant.
5. Go to **Settings → Devices & Services** in Home Assistant, click **Add Integration**, and select **Suptronics X120x**.
6. Verify that the battery sensors, binary sensor, and switch are now present.

### Troubleshooting & Logging
If something doesn’t work as expected, enable debug logging in `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.suptronics_ups_x120x: debug
