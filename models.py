"""
Data models for the lift simulation.

This module defines the ``LiftModel`` and ``DoorModel`` classes that
encapsulate the state and behaviour of the elevator cabin and its
doors.  They are intentionally free of any GUI code and can be used
from both a graphical interface and automated tests.
"""

from typing import List, Tuple


class LiftModel:
    """Represents the state and behaviour of a lift (elevator) cabin."""

    def __init__(
        self,
        num_floors: int,
        field_height: float,
        lift_height: float,
        floor_height: float,
        floor_spacing: float,
        normal_speed: float,
        slow_speed: float,
    ) -> None:
        """
        Initialize a new ``LiftModel`` instance.

        Parameters
        ----------
        num_floors: int
            Total number of floors served by the lift.
        field_height: float
            Height of the scene in which the lift moves.
        lift_height: float
            Height of the lift cabin.
        floor_height: float
            Height of a single floor.
        floor_spacing: float
            Vertical spacing between floors.
        normal_speed: float
            Lift speed in normal mode (pixels per tick).
        slow_speed: float
            Lift speed in slow mode (pixels per tick).
        """
        self.num_floors = num_floors
        self.field_height = field_height
        self.lift_height = lift_height
        self.floor_height = floor_height
        self.floor_spacing = floor_spacing

        # Compute the border spacing so that floors are centred vertically
        self.border_spacing = (
            field_height
            - (num_floors * floor_height)
            - floor_spacing * (num_floors - 1)
        ) / 2

        # Position of the cabin (vertical centre, Y coordinate from top down)
        self.position: float = field_height / 2
        self.normal_speed = normal_speed
        self.slow_speed = slow_speed
        self.current_speed = self.normal_speed

        # Precompute sensor positions for each floor (top, centre, bottom).
        # Floors are indexed from 0 (bottom) to num_floors-1 (top).  The
        # coordinate system starts at the top of the field, so to arrange
        # floors from bottom to top we compute base_y from the bottom up.
        self.sensors: List[List[float]] = []
        for floor in range(num_floors):
            # Compute the top of this floor measured from the top of the scene.
            # Bottom floor has index 0 and should be drawn above the bottom border spacing.
            base_y = (
                self.field_height
                - self.border_spacing
                - (floor + 1) * floor_height
                - floor * floor_spacing
            )
            top = base_y
            centre = base_y + floor_height / 2
            bottom = base_y + floor_height
            self.sensors.append([top, centre, bottom])

    def move_up(self) -> None:
        """Move the cabin upwards by the current speed."""
        self.position -= self.current_speed
        # Clamp to the topmost position
        self.position = max(self.position, self.lift_height / 2)

    def move_down(self) -> None:
        """Move the cabin downwards by the current speed."""
        self.position += self.current_speed
        # Clamp to the bottommost position
        self.position = min(self.position, self.field_height - self.lift_height / 2)

    def toggle_slow(self, enabled: bool) -> None:
        """Switch between normal and slow speeds."""
        self.current_speed = self.slow_speed if enabled else self.normal_speed

    def get_active_floor_sensors(self) -> List[List[bool]]:
        """Return a matrix indicating which floor sensors are active.

        The result is a list with one sublist per floor; each sublist
        contains three booleans corresponding to the top, centre and
        bottom sensors of that floor.  A sensor is considered active
        when the lift's centre is within ``2 * current_speed`` pixels
        of the sensor position.
        """
        lift_center = self.position
        tol = self.current_speed * 2
        active: List[List[bool]] = []
        for floor_sensors in self.sensors:
            active.append([abs(lift_center - y) <= tol for y in floor_sensors])
        return active

    def top_limit(self) -> float:
        """Return the y-coordinate of the topmost floor's top sensor."""
        # Topmost floor is at the end of the sensors list
        return self.sensors[-1][0]

    def bottom_limit(self) -> float:
        """Return the y-coordinate of the bottommost floor's bottom sensor."""
        # Bottommost floor is at index 0
        return self.sensors[0][2]

    def is_on_floor_center(self) -> bool:
        """Return True if the cabin is aligned with any floor centre sensor."""
        active = self.get_active_floor_sensors()
        return any(row[1] for row in active)


class DoorModel:
    """Represents the state and behaviour of a sliding lift door."""

    def __init__(self, opening_w: float, speed_norm: float) -> None:
        """
        Initialize a new ``DoorModel``.

        Parameters
        ----------
        opening_w: float
            Width of the door opening (pixels).  The full door leaf
            width will be equal to this value.
        speed_norm: float
            Fraction of the door's travel to move per tick (0–1).
        """
        self.opening_w = opening_w
        self.leaf_w = opening_w  # width of the door leaf equals opening
        # ``left_norm`` ranges from 0.0 (closed) to 1.0 (fully open)
        self.left_norm: float = 0.0
        self.speed_norm = speed_norm

    def open_step(self) -> None:
        """Advance the door towards the fully open position."""
        self.left_norm += self.speed_norm
        if self.left_norm > 1.0:
            self.left_norm = 1.0

    def close_step(self) -> None:
        """Advance the door towards the fully closed position."""
        self.left_norm -= self.speed_norm
        if self.left_norm < 0.0:
            self.left_norm = 0.0

    def get_leaf_left_px(self, cabin_left_px: float) -> float:
        """Return the x-coordinate of the left edge of the door leaf.

        The returned position is the cabin's left position plus the
        door's normalised offset multiplied by the opening width.
        """
        return cabin_left_px + self.left_norm * self.opening_w

    def get_edge_sensors_active(self) -> Tuple[bool, bool]:
        """Return booleans indicating whether the door is fully closed/open.

        Returns
        -------
        (bool, bool)
            A tuple ``(closed_ok, open_ok)`` where ``closed_ok`` is True
            when the door is at the fully closed position (within a
            tolerance based on ``speed_norm``), and ``open_ok`` is True
            when the door is fully open.
        """
        tol = self.speed_norm * 2
        left_ok = abs(self.left_norm - 0.0) <= tol
        right_ok = abs(self.left_norm - 1.0) <= tol
        return left_ok, right_ok


__all__ = ["LiftModel", "DoorModel"]