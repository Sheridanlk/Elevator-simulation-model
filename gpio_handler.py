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

    def __init__(self, config: Optional[dict] = None) -> None:
        self.config = config or GPIO_CONFIG
        self.enabled: bool = bool(self.config.get("enable", False))
        self.gpio = _GPIO

        # Cache pin assignments
        outputs = self.config.get("outputs", {})
        self.floor_sensor_pins: List[List[int]] = outputs.get("floor_sensors", [])
        self.door_sensor_pins: List[int] = outputs.get("door_sensors", [])
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
        for pair in self.door_sensor_pins:
            if len(pair) > 0 and pair[0] is not None:
                self.gpio.setup(pair[0], self.gpio.OUT)
            if len(pair) > 1 and pair[1] is not None:
                self.gpio.setup(pair[1], self.gpio.OUT)
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
        if self.enabled:
            try:
                self.gpio.cleanup()
            except Exception:
                pass

    # ------------------------ Output operations -------------------------
    def update_floor_sensors(self, states: List[List[bool]]) -> None:
        if not self.enabled:
            return
        for floor_idx, row in enumerate(self.floor_sensor_pins):
            for sensor_idx, pin in enumerate(row):
                if pin is None:
                    continue
                try:
                    state = states[floor_idx][sensor_idx]
                except Exception:
                    state = False
                self.gpio.output(pin, self.gpio.HIGH if state else self.gpio.LOW)

    def update_door_sensors(self, closed_ok: bool, open_ok: bool) -> None:
        if not self.enabled:
            return
        try:
            pins = self.door_sensor_pins
            if not pins:
                return

            closed_pin = pins[0]
            open_pin = pins[1] if len(pins) > 1 else None

            if closed_pin is not None:
                self.gpio.output(
                    closed_pin,
                    self.gpio.HIGH if closed_ok else self.gpio.LOW,
                )
            if open_pin is not None:
                self.gpio.output(
                    open_pin,
                    self.gpio.HIGH if open_ok else self.gpio.LOW,
                )

        except Exception as e:
            print("[GPIO] error in update_door_sensors:", e)
    def update_cabin_buttons(self, states: List[bool]) -> None:
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