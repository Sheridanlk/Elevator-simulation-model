import os
import yaml
from typing import Any, Dict


def _scale(value: float, k: float) -> float:
    return value * k


def _load_raw_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config() -> Dict[str, Any]:
    # Determine the path to the YAML file relative to this module
    current_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(current_dir, "config.yaml")

    raw = _load_raw_config(yaml_path)

    # Extract the global scale factor; default to 1 if not specified
    k = float(raw.get("k", 1))

    # Build the processed configuration dictionary
    cfg: Dict[str, Any] = {}
    cfg["k"] = k
    # Field
    field = raw.get("field", {})
    cfg["field_width"] = _scale(float(field.get("width", 0)), k)
    cfg["field_height"] = _scale(float(field.get("height", 0)), k)
    # Floors
    cfg["num_floors"] = int(raw.get("num_floors", 0))
    cfg["floor_height"] = _scale(float(raw.get("floor_height", 0)), k)
    cfg["floor_spacing"] = _scale(float(raw.get("floor_spacing", 0)), k)
    # Lift
    lift = raw.get("lift", {})
    cfg["lift_width"] = _scale(float(lift.get("width", 0)), k)
    cfg["lift_height"] = _scale(float(lift.get("height", 0)), k)
    # Speeds
    speeds = raw.get("speeds", {})
    cfg["normal_speed"] = _scale(float(speeds.get("normal", 0)), k)
    cfg["slow_speed"] = _scale(float(speeds.get("slow", 0)), k)
    # Door speed (fraction per tick) does not depend on k
    cfg["door_speed_norm"] = float(raw.get("door_speed_norm", 0))
    # Lamp radius
    cfg["lamp_radius"] = _scale(float(raw.get("lamp_radius", 0)), k)

    return cfg


# Load the configuration at module import time.  Clients can import
# ``CONFIG`` and use it directly without calling ``load_config``.
CONFIG: Dict[str, Any] = load_config()

__all__ = ["CONFIG", "load_config"]