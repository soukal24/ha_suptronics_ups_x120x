# Changelog

All notable changes to this project will be documented in this file.  
Use it as both the changelog and the release notes for GitHub.

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
