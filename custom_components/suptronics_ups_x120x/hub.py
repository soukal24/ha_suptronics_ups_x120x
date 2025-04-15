import logging
import gpiod
from datetime import timedelta
from gpiod.line import Direction, Value, Bias, Drive, Edge, Clock

_LOGGER = logging.getLogger(__name__)

class SuptronicsHub:
    """
    Helper class that maintains a reference to the GPIO chip and provides 
    methods to request lines for sensors/switches.
    """

    def __init__(self):
        _LOGGER.debug("SuptronicsHub init: opening /dev/gpiochip0")
        # Replace "/dev/gpiochip0" if your device has a different chip.
        self._chip = gpiod.Chip("/dev/gpiochip0")
        self._online = True

    @property
    def online(self):
        """Returns True if the hub is initialized without errors."""
        return self._online

    def add_sensor(self, port, active_low, bounce_ms=50):
        """
        Requests a GPIO line for a sensor input (e.g., power loss). 
        Sets up debouncing and edge detection.
        Returns (line_request, initial_is_on_state).
        """
        cfg = gpiod.LineSettings(
            direction=Direction.INPUT,
            active_low=active_low,
            bias=Bias.PULL_UP,
            edge_detection=Edge.BOTH,
            debounce_period=timedelta(milliseconds=bounce_ms),
            event_clock=Clock.REALTIME
        )
        line_request = self._chip.request_lines(
            consumer="suptronics_x120x_sensor",
            config={port: cfg}
        )
        val = line_request.get_value(port)
        is_on = (val == Value.ACTIVE)
        return line_request, is_on

    def add_switch(self, port, active_low, init_state):
        """
        Requests a GPIO line for a switch (output).
        We set the initial output state to ACTIVE or INACTIVE based on init_state.
        """
        cfg = gpiod.LineSettings(
            direction=Direction.OUTPUT,
            active_low=active_low,
            bias=Bias.AS_IS,
            drive=Drive.PUSH_PULL,
            output_value=Value.ACTIVE if init_state else Value.INACTIVE
        )
        line_request = self._chip.request_lines(
            consumer="suptronics_x120x_switch",
            config={port: cfg}
        )
        return line_request

    def turn_on(self, line_req, port):
        """
        Sets the specified GPIO line to ACTIVE, effectively turning the switch 'on'.
        """
        line_req.set_value(port, Value.ACTIVE)

    def turn_off(self, line_req, port):
        """
        Sets the specified GPIO line to INACTIVE, effectively turning the switch 'off'.
        """
        line_req.set_value(port, Value.INACTIVE)
