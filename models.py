from typing import List, Tuple


class LiftModel:

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

        # Position of the cabin (vertical centre, Y coordinate from bottom up)
        self.position: float = field_height / 2
        self.normal_speed = normal_speed
        self.slow_speed = slow_speed
        self.current_speed = self.normal_speed

        # Precompute sensor positions for each floor (top, centre, bottom).
        # Floors are indexed from 0 (bottom) to num_floors-1 (top).
        # Coordinate system here: origin at bottom of the field, Y increases upwards.
        self.sensors: List[List[float]] = []
        for floor in range(num_floors):
            # Bottom of this floor measured from the bottom of the field
            floor_bottom = self.border_spacing + floor * (floor_height + floor_spacing)
            bottom = floor_bottom
            centre = floor_bottom + floor_height / 2
            top = floor_bottom + floor_height
            self.sensors.append([top, centre, bottom])

    def move_up(self) -> None:
        self.position += self.current_speed
        # Clamp to the topmost position
        self.position = min(self.position, self.field_height - self.lift_height / 2)

    def move_down(self) -> None:
        self.position -= self.current_speed
        # Clamp to the bottommost position
        self.position = max(self.position, self.lift_height / 2)

    def toggle_slow(self, enabled: bool) -> None:
        self.current_speed = self.slow_speed if enabled else self.normal_speed

    def get_active_floor_sensors(self) -> List[List[bool]]:
        lift_center = self.position
        tol = self.current_speed * 2
        active: List[List[bool]] = []
        for floor_sensors in self.sensors:
            active.append([abs(lift_center - y) <= tol for y in floor_sensors])
        return active

    def top_limit(self) -> float:
        # Topmost floor is at the end of the sensors list
        return self.sensors[-1][0]

    def bottom_limit(self) -> float:
        # Bottommost floor is at index 0
        return self.sensors[0][2]

    def is_on_floor_center(self) -> bool:
        active = self.get_active_floor_sensors()
        return any(row[1] for row in active)


class DoorModel:
    def __init__(self, opening_w: float, speed_norm: float) -> None:
        self.opening_w = opening_w
        self.leaf_w = opening_w  # width of the door leaf equals opening
        # ``left_norm`` ranges from 0.0 (closed) to 1.0 (fully open)
        self.left_norm: float = 0.0
        self.speed_norm = speed_norm

    def open_step(self) -> None:
        self.left_norm += self.speed_norm
        if self.left_norm > 1.0:
            self.left_norm = 1.0

    def close_step(self) -> None:
        self.left_norm -= self.speed_norm
        if self.left_norm < 0.0:
            self.left_norm = 0.0

    def get_leaf_left_px(self, cabin_left_px: float) -> float:
        return cabin_left_px + self.left_norm * self.opening_w

    def get_edge_sensors_active(self) -> Tuple[bool, bool]:
        tol = self.speed_norm * 2
        left_ok = abs(self.left_norm - 0.0) <= tol
        right_ok = abs(self.left_norm - 1.0) <= tol
        return left_ok, right_ok


__all__ = ["LiftModel", "DoorModel"]