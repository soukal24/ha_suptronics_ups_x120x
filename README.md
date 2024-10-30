# Suptronics UPS X120x Home Assistant Integration

Supports boards X1200, X1201, and X1202 for complete monitoring and management of your Suptronics UPS.

This is a Home Assistant integration for monitoring and managing the Suptronics UPS X120x. It provides real-time insights into battery level and voltage, ensuring your system remains safe and operational.

This repository contains the Home Assistant integration for the Suptronics UPS X120x, allowing you to monitor the battery charge and voltage of your Suptronics UPS directly from Home Assistant.

![UPS Integration Screenshot](ups.png)

## Features
- Monitor UPS battery level as a percentage.
- Monitor UPS battery voltage in volts.
- Automatically updates sensor readings.

## Installation

1. **Manual Installation**
   - Download the `suptronics_ups_x120x` folder.
   - Copy the folder into your Home Assistant `custom_components` directory.

2. **Enable I2C**
   - **HassOS**: To enable I2C in Home Assistant OS System, follow the [official instructions](https://www.home-assistant.io/common-tasks/os/#enable-i2c) or use the [HassOS I2C Configurator addon](https://community.home-assistant.io/t/add-on-hassos-i2c-configurator/264167).
   - **Home Assistant Core**:
     - Enable the I2C interface using the Raspberry Pi configuration utility:
       ```sh
       # pi user environment: Enable i2c interface
       $ sudo raspi-config
       ```
       Select `Interfacing options -> I2C`, choose `<Yes>` and hit Enter, then go to Finish and you'll be prompted to reboot.

     - Install dependencies for using the `smbus-cffi` module and enable your `homeassistant` user to join the I2C group:
       ```sh
       # pi user environment: Install i2c dependencies and utilities
       $ sudo apt-get install build-essential libi2c-dev i2c-tools python-dev libffi-dev

       # pi user environment: Add homeassistant user to the i2c group
       $ sudo addgroup homeassistant i2c

       # pi user environment: Reboot Raspberry Pi to apply changes
       $ sudo reboot
       ```

     - **Check the I2C Address of the Sensor**
       - Using **HassOS I2C Configurator**: You may use [HassOS I2C Configurator](https://community.home-assistant.io/t/add-on-hassos-i2c-configurator/264167) to activate I2C on your Hass host and search available device addresses.
       - Using **i2c-tools**: After installing `i2c-tools`, a utility is available to scan the addresses of connected sensors:
         ```sh
         /usr/sbin/i2cdetect -y 1
         ```
         It will output a table like this:
         ```
              0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
         00:          -- -- -- -- -- -- -- -- -- -- -- -- --
         10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
         20: -- -- -- 23 -- -- -- -- -- -- -- -- -- -- -- --
         30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
         40: 40 -- -- -- -- -- UU -- -- -- -- -- -- -- -- --
         50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
         60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
         70: -- -- -- -- -- -- -- 77
         ```

3. **Configuration**
   Add the following to your `configuration.yaml` file:
   ```yaml
   suptronics_ups_x120x:
   ```

   If you would like to make the X120x board fully controllable and set up automation for preventing battery overcharging or for safe shutdown on power loss, you can optionally install the [Raspberry Pi GPIO integration](https://github.com/thecode/ha-rpi_gpio) and add the following configuration:
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
   This setup allows for control and monitoring of power loss and charging state, making the board more versatile for different use cases.

4. **Restart Home Assistant**
   - Restart Home Assistant to load the new integration.

## Configuration
No further configuration is required after installation. The integration will automatically set up the necessary sensors.

## Sensors
The following sensors are created by this integration:

- **UPS Battery Level** (`sensor.ups_battery_level`): Reports the current charge level of the UPS battery as a percentage.
- **UPS Battery Voltage** (`sensor.ups_battery_voltage`): Reports the current battery voltage in volts.

## Debugging
If you encounter any issues during setup, you can enable debugging by adding the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.suptronics_ups_x120x: debug
```

## Example Usage
After setting up the integration, you can use the sensors to automate tasks or monitor the state of your UPS. For example:

- Send a notification when the battery level drops below a certain threshold.
- Track battery voltage over time using Home Assistant's built-in history features.

For extended functionality, such as controlling the charging process or detecting power loss, you can use the optional Raspberry Pi GPIO integration to add relevant sensors and switches.

- Automatically turn off charging when the battery is fully charged to prevent overcharging.
- Safely shut down the system when power loss is detected to prevent damage.

## Support

If you're interested in this project, please note that I am not an experienced programmer. Most of this integration was created out of desperation and with the help of AI. I would be very grateful if someone could take over this project and help improve it further.
If you encounter any issues, please feel free to open an issue on this repository. Contributions are welcome!

## License
This project is licensed under the MIT License.

