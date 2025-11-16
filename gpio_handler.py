"""
GPIO abstraction layer for the lift simulation.

This module provides a ``GPIOHandler`` class that wraps access to
RPi.GPIO and exposes methods to set the state of sensors and buttons
configured in the GPIO configuration.  When GPIO is disabled or
RPi.GPIO is unavailable, the handler falls back to a dummy
implementation that logs operations instead of touching hardware.

The handler should be instantiated at application startup and can be
used by the view or controller layers to update physical outputs.
"""

from typing import List, Optional, Tuple
from gpio_config import GPIO_CONFIG


try:
    import RPi.GPIO as _GPIO
except Exception:
    # Define a dummy GPIO module when running on systems without physical GPIO
    class _DummyGPIO:
        BOARD = "BOARD"
        BCM = "BCM"
        OUT = "OUT"
        IN = "IN"
        LOW = 0
        HIGH = 1
        PUD_UP = "PUD_UP"
        PUD_DOWN = "PUD_DOWN"

        def setmode(self, mode):
            print(f"[GPIO] setmode({mode}) called (dummy)")

        def setup(self, channel, mode, pull_up_down=None):
            print(f"[GPIO] setup(channel={channel}, mode={mode}, pud={pull_up_down}) called (dummy)")

        def output(self, channel, state):
            print(f"[GPIO] output(channel={channel}, state={state}) called (dummy)")

        def input(self, channel):
            print(f"[GPIO] input(channel={channel}) called (dummy)")
            return 0

        def cleanup(self):
            print("[GPIO] cleanup() called (dummy)")

    _GPIO = _DummyGPIO()  # type: ignore


class GPIOHandler:
    """Wrapper around RPi.GPIO providing high-level operations for the lift."""

    def __init__(self, config: Optional[dict] = None) -> None:
        """
        Initialise the handler from the provided configuration.  If
        ``config`` is None, the global ``GPIO_CONFIG`` is used.

        Parameters
        ----------
        config: dict, optional
            GPIO configuration dictionary.  If omitted, the loader
            ``gpio_config.GPIO_CONFIG`` is used.
        """
        self.config = config or GPIO_CONFIG
        self.enabled: bool = bool(self.config.get("enable", False))
        self.gpio = _GPIO
        # Cache pin assignments
        outputs = self.config.get("outputs", {})
        self.floor_sensor_pins: List[List[int]] = outputs.get("floor_sensors", [])
        self.cabin_button_pins: List[int] = outputs.get("cabin_buttons", [])
        self.floor_button_pins: List[int] = outputs.get("floor_buttons", [])
        inputs = self.config.get("inputs", {})
        self.input_pins = {
            "up": inputs.get("up"),
            "down": inputs.get("down"),
            "open_door": inputs.get("open_door"),
            "close_door": inputs.get("close_door"),
            "slow_mode": inputs.get("slow_mode"),
        }
        # Keep track of whether setup() has been called
        self._setup_done = False

    def setup(self) -> None:
        """Initialise GPIO pins according to the configuration."""
        if not self.enabled:
            return
        if self._setup_done:
            return
        # Use BCM numbering scheme
        self.gpio.setmode(self.gpio.BCM)
        # Setup output pins
        for row in self.floor_sensor_pins:
            for pin in row:
                if pin is not None:
                    self.gpio.setup(pin, self.gpio.OUT)
                    self.gpio.output(pin, self.gpio.LOW)
        for pin in self.cabin_button_pins:
            if pin is not None:
                self.gpio.setup(pin, self.gpio.OUT)
                self.gpio.output(pin, self.gpio.LOW)
        for pin in self.floor_button_pins:
            if pin is not None:
                self.gpio.setup(pin, self.gpio.OUT)
                self.gpio.output(pin, self.gpio.LOW)
        # Setup input pins with pull-down resistors (if defined)
        for key, pin in self.input_pins.items():
            if pin is not None:
                self.gpio.setup(pin, self.gpio.IN, pull_up_down=self.gpio.PUD_DOWN)
        self._setup_done = True

    def cleanup(self) -> None:
        """Clean up GPIO pins on application exit."""
        if self.enabled:
            try:
                self.gpio.cleanup()
            except Exception:
                pass

    # ------------------------ Output operations -------------------------
    def update_floor_sensors(self, states: List[List[bool]]) -> None:
        """Set the floor sensor outputs according to the provided state matrix.

        Parameters
        ----------
        states: list of list of bool
            A 2D list matching the structure of ``floor_sensor_pins``.
            Each boolean controls the corresponding GPIO pin: True
            drives the pin HIGH, False drives it LOW.  If a pin is
            ``None`` or missing, it is skipped.
        """
        if not self.enabled:
            return
        for floor_idx, row in enumerate(self.floor_sensor_pins):
            for sensor_idx, pin in enumerate(row):
                if pin is None:
                    continue
                # Determine the desired state; default to False if missing
                try:
                    state = states[floor_idx][sensor_idx]
                except Exception:
                    state = False
                self.gpio.output(pin, self.gpio.HIGH if state else self.gpio.LOW)

    def update_cabin_buttons(self, states: List[bool]) -> None:
        """Set the cabin button outputs based on the provided boolean list."""
        if not self.enabled:
            return
        for idx, pin in enumerate(self.cabin_button_pins):
            if pin is None:
                continue
            try:
                state = states[idx]
            except Exception:
                state = False
            self.gpio.output(pin, self.gpio.HIGH if state else self.gpio.LOW)

    def update_floor_buttons(self, states: List[bool]) -> None:
        """Set the external floor call button outputs."""
        if not self.enabled:
            return
        for idx, pin in enumerate(self.floor_button_pins):
            if pin is None:
                continue
            try:
                state = states[idx]
            except Exception:
                state = False
            self.gpio.output(pin, self.gpio.HIGH if state else self.gpio.LOW)

    # ------------------------ Input operations -------------------------
    def read_inputs(self) -> dict:
        """Read and return the current values of all input pins.

        Returns
        -------
        dict
            A dictionary mapping each input name ("up", "down", etc.)
            to a boolean value.  When GPIO is disabled, all values are False.
        """
        values = {}
        if not self.enabled:
            for key in self.input_pins:
                values[key] = False
            return values
        for key, pin in self.input_pins.items():
            if pin is None:
                values[key] = False
            else:
                try:
                    values[key] = bool(self.gpio.input(pin))
                except Exception:
                    values[key] = False
        return values


__all__ = ["GPIOHandler"]