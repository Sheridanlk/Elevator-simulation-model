"""
LiftController module to centralize the logic for controlling the lift, door,
sensors and GPIO interactions.  This class encapsulates all stateful
behaviour that was previously spread across the view.  The controller
receives commands from either the GUI or hardware inputs, updates the
models accordingly, performs safety checks, and manages sensor states.  It
also exposes helper methods for the view to query the current state of
the system.

The goal of this module is to separate concerns: the controller handles
business logic, the models represent the physical state, the GPIO handler
abstracts hardware interactions, and the view is responsible only for
presentation.  Clients of LiftController should not mutate the models
directly; instead, they should invoke the appropriate methods on the
controller.  Optionally, an alarm callback may be provided to handle
error conditions such as moving with an open door or attempting to open
the door off-floor.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from models import LiftModel, DoorModel
from gpio_handler import GPIOHandler


class LiftController:
    """Central controller for the lift system.

    This class aggregates all state and logic needed to operate the lift and
    door models in response to commands from the GUI or hardware (GPIO).
    It keeps track of separate sources of control (GUI vs. GPIO) and
    computes effective actions based on those inputs.  All safety checks
    (like preventing motion with an open door or disallowing door opening
    off-floor) are performed here before the models are mutated.  Sensor
    states are updated in one place and written to GPIO outputs when
    enabled.
    """

    def __init__(
        self,
        lift_model: LiftModel,
        door_model: DoorModel,
        gpio_handler: Optional[GPIOHandler] = None,
        alarm_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.lift_model = lift_model
        self.door_model = door_model
        self.gpio_handler = gpio_handler
        # Callback invoked on alarm conditions.  Signature: (key, message).
        self.alarm_callback = alarm_callback

        # Flags for movement control.  Separate flags track commands from the
        # GUI and from GPIO.  The effective movement flags (self.moving_up and
        # self.moving_down) are computed from these.
        self.gui_moving_up = False
        self.gui_moving_down = False
        self.gpio_moving_up = False
        self.gpio_moving_down = False
        self.moving_up = False
        self.moving_down = False

        # Flags for door control.
        self.gui_opening = False
        self.gui_closing = False
        self.gpio_opening = False
        self.gpio_closing = False
        self.opening = False
        self.closing = False

        # Slow mode flags.  ``gui_slow_enabled`` represents the state
        # requested by the GUI checkbox.  ``gpio_slow_enabled`` represents
        # the state forced by the hardware slow_mode input.  The lift
        # model's speed is toggled based on these values.
        self.gui_slow_enabled = False
        self.gpio_slow_enabled = False
        # Ensure the model starts in normal speed mode.
        self.lift_model.toggle_slow(False)

    # ------------------------------------------------------------------
    # Helpers for updating effective flags
    # ------------------------------------------------------------------
    def _update_motion_flags(self) -> None:
        """Recompute the effective movement flags from GUI and GPIO flags."""
        prev_up = self.moving_up
        prev_down = self.moving_down

        self.moving_up = self.gui_moving_up or self.gpio_moving_up
        self.moving_down = self.gui_moving_down or self.gpio_moving_down

    def _update_door_flags(self) -> None:
        """Recompute the effective door movement flags from GUI and GPIO flags."""
        self.opening = self.gui_opening or self.gpio_opening
        self.closing = self.gui_closing or self.gpio_closing

    # ------------------------------------------------------------------
    # GUI command handlers
    # ------------------------------------------------------------------
    def start_move_up(self) -> None:
        """Request the cabin to move upwards from the GUI."""
        # Safety: prevent moving with an open door
        left_ok, _ = self.door_model.get_edge_sensors_active()
        if not left_ok:
            # Door is not fully closed; raise alarm
            self._alarm("move_with_open_door", "Авария: движение с открытой дверью.")
        # Set GUI movement flags
        self.gui_moving_up = True
        self.gui_moving_down = False
        self._update_motion_flags()

    def start_move_down(self) -> None:
        """Request the cabin to move downwards from the GUI."""
        left_ok, _ = self.door_model.get_edge_sensors_active()
        if not left_ok:
            self._alarm("move_with_open_door", "Авария: движение с открытой дверью.")
        self.gui_moving_down = True
        self.gui_moving_up = False
        self._update_motion_flags()

    def stop_move(self) -> None:
        """Stop cabin movement requested from the GUI."""
        self.gui_moving_up = False
        self.gui_moving_down = False
        self._update_motion_flags()

    def toggle_slow_mode(self, enabled: bool) -> None:
        """Toggle slow mode requested from the GUI.

        If the hardware slow input is active, the GUI request is ignored and
        the checkbox should be forced back to checked state by the view.  The
        view should consult ``gpio_slow_enabled`` to adjust its UI.  When
        slow mode is toggled via GUI, update the lift model speed accordingly.
        """
        # If slow mode is forced by hardware, ignore GUI toggles.
        if self.gpio_slow_enabled:
            return
        self.gui_slow_enabled = enabled
        self.lift_model.toggle_slow(self.gui_slow_enabled)

    def start_open_door(self) -> None:
        """Request to open the door from the GUI."""
        # Safety: door should not open while moving or off-floor.
        if self.moving_up or self.moving_down:
            self._alarm(
                "open_while_moving",
                "Авария: попытка открыть дверь во время движения.",
            )
        if not self.lift_model.is_on_floor_center():
            self._alarm(
                "open_off_floor",
                "Авария: попытка открыть дверь вне этажа.",
            )
        self.gui_opening = True
        self.gui_closing = False
        self._update_door_flags()

    def start_close_door(self) -> None:
        """Request to close the door from the GUI."""
        self.gui_closing = True
        self.gui_opening = False
        self._update_door_flags()

    def stop_door(self) -> None:
        """Stop door movement requested from the GUI."""
        self.gui_opening = False
        self.gui_closing = False
        self._update_door_flags()

    # ------------------------------------------------------------------
    # GPIO command handlers
    # ------------------------------------------------------------------
    def _alarm(self, key: str, text: str) -> None:
        """Invoke the alarm callback if provided."""
        if self.alarm_callback:
            try:
                self.alarm_callback(key, text)
            except Exception:
                pass

    def poll_gpio_inputs(self) -> Tuple[List[bool], List[bool]]:
        """Poll discrete inputs from the GPIO handler and update flags.

        Returns a tuple of (cabin_lamp_states, floor_lamp_states) so the view
        can update lamp indicators accordingly.  If GPIO is disabled or
        unavailable, both lists will contain ``False`` values.
        """
        if self.gpio_handler is None:
            # Return dummy lamp states
            return [False] * len(self.gpio_handler.cabin_lamp_input_pins) if hasattr(self.gpio_handler, "cabin_lamp_input_pins") else [], [False] * len(self.gpio_handler.floor_lamp_input_pins) if hasattr(self.gpio_handler, "floor_lamp_input_pins") else []

        # Read raw input states
        inputs = self.gpio_handler.read_inputs()
        move_up = bool(inputs.get("up", False))
        move_down = bool(inputs.get("down", False))
        slow = bool(inputs.get("slow_mode", False))
        door_open = bool(inputs.get("open_door", False))
        door_close = bool(inputs.get("close_door", False))

        # Update movement flags from GPIO.  Resolve conflict by doing nothing.
        if move_up or move_down:
            if move_up and move_down:
                self.gpio_moving_up = False
                self.gpio_moving_down = False
            else:
                self.gpio_moving_up = move_up
                self.gpio_moving_down = move_down
        else:
            # No movement requested
            self.gpio_moving_up = False
            self.gpio_moving_down = False
        self._update_motion_flags()

        # Update door flags from GPIO
        if door_open or door_close:
            if door_open and not door_close:
                # Request opening
                if self.moving_up or self.moving_down:
                    self._alarm(
                        "open_while_moving",
                        "Авария: попытка открыть дверь во время движения.",
                    )
                if not self.lift_model.is_on_floor_center():
                    self._alarm(
                        "open_off_floor",
                        "Авария: попытка открыть дверь вне этажа.",
                    )
                self.gpio_opening = True
                self.gpio_closing = False
            elif door_close and not door_open:
                # Request closing
                self.gpio_closing = True
                self.gpio_opening = False
            else:
                # Ambiguous or invalid input: stop door
                self.gpio_opening = False
                self.gpio_closing = False
        else:
            # No door command
            self.gpio_opening = False
            self.gpio_closing = False
        self._update_door_flags()

        # Handle slow mode from GPIO.  Hardware forces slow when active.
        if slow:
            if not self.gpio_slow_enabled:
                # Force slow mode on
                self.gpio_slow_enabled = True
                self.lift_model.toggle_slow(True)
        else:
            # Hardware slow input inactive
            if self.gpio_slow_enabled:
                # Clear forced slow; restore GUI state
                self.gpio_slow_enabled = False
                self.lift_model.toggle_slow(self.gui_slow_enabled)

        # Read lamp states from GPIO inputs (button lamps).  This is
        # forwarded to the view for updating the appearance of cabin and
        # floor call buttons.  If reading fails, return empty lists.
        try:
            cabin_lamps, floor_lamps = self.gpio_handler.read_button_lamps()
        except Exception:
            cabin_lamps, floor_lamps = [], []
        return cabin_lamps, floor_lamps

    # ------------------------------------------------------------------
    # Impulse methods for cabin and floor buttons
    # ------------------------------------------------------------------
    def cabin_button_pressed(self, idx: int) -> None:
        """Send a short pulse to the cabin button output."""
        if self.gpio_handler is None:
            return
        # High pulse followed by low
        self.gpio_handler.set_cabin_button_output(idx, True)
        # Using a timer inside the controller is not possible; the view must
        # schedule the reset.  The view is responsible for scheduling the
        # callback after a short delay.

    def floor_button_clicked(self, idx: int) -> None:
        """Send a short pulse to the floor call button output."""
        if self.gpio_handler is None:
            return
        self.gpio_handler.set_floor_button_output(idx, True)
        # See comment in cabin_button_pressed about scheduling reset.

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------
    def is_any_active(self) -> bool:
        """Return True if any movement or door operation is in progress."""
        return self.moving_up or self.moving_down or self.opening or self.closing

    def get_floor_sensor_states(self) -> List[List[bool]]:
        """Compute the current floor sensor states from the lift model."""
        return self.lift_model.get_active_floor_sensors()

    def get_door_sensor_states(self) -> Tuple[bool, bool]:
        """Return the (closed_ok, open_ok) door sensor flags."""
        return self.door_model.get_edge_sensors_active()

    def tick(self) -> Tuple[List[List[bool]], Tuple[bool, bool]]:

        # Передвжидение кабины 
        if self.moving_up:
            self.lift_model.move_up()
        if self.moving_down:
            self.lift_model.move_down()
        # Boundary checks
        try:
            top_lim = self.lift_model.top_limit()
            bot_lim = self.lift_model.bottom_limit()
        except Exception:
            top_lim = None
            bot_lim = None
        # Top limit alarm
        if top_lim is not None and self.moving_up and self.lift_model.position >= top_lim:
            self._alarm(
                "going_beyond",
                "Выход за верхний предел: сработал верхний аварийный датчик.",
            )
        # Bottom limit alarm
        if bot_lim is not None and self.moving_down and self.lift_model.position <= bot_lim:
            self._alarm(
                "going_beyond",
                "Выход за нижний предел: сработал нижний аварийный датчик.",
            )
        # Movement for the door
        if self.opening and self.door_model.left_norm < 1.0:
            self.door_model.open_step()
        if self.closing and self.door_model.left_norm > 0.0:
            self.door_model.close_step()

        # Compute sensor states
        active_floor = self.lift_model.get_active_floor_sensors()
        door_closed_ok, door_open_ok = self.door_model.get_edge_sensors_active()

        # Update sensors on GPIO outputs if enabled
        if self.gpio_handler is not None:
            try:
                self.gpio_handler.update_floor_sensors(active_floor)
                self.gpio_handler.update_door_sensors(door_closed_ok, door_open_ok)
            except Exception:
                pass

        return active_floor, (door_closed_ok, door_open_ok)
