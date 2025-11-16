"""
Configuration loader for the lift simulation.

This module reads ``config.yaml`` from the same directory as the
Python source files and exposes a single dictionary called
``CONFIG``.  All linear dimensions and speeds defined in the YAML
file are multiplied by the global scale factor ``k`` on load.  The
resulting values can be passed directly to model and view classes.

Example usage::

    from config import CONFIG
    print(CONFIG['field_width'])
    print(CONFIG['lift_width'])

The YAML file should contain keys documented in the provided
``config.yaml``.  If the file cannot be read or parsed, an
``IOError`` or ``yaml.YAMLError`` will be raised on import.
"""

import os
import yaml
from typing import Any, Dict


def _scale(value: float, k: float) -> float:
    """Scale a numeric value by the global factor ``k``."""
    return value * k


def _load_raw_config(path: str) -> Dict[str, Any]:
    """Load the raw YAML configuration from ``path`` and return it.

    Parameters
    ----------
    path: str
        Absolute path to the YAML configuration file.

    Returns
    -------
    dict
        Parsed Python representation of the YAML content.
    """
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config() -> Dict[str, Any]:
    """Load and post-process the lift simulation configuration.

    The function reads ``config.yaml`` located in the same directory
    as this module, multiplies lengths and speeds by ``k``, and
    returns a flat dictionary with convenient keys.  The resulting
    dictionary includes the following keys:

    - ``k``: the global scale factor
    - ``field_width`` and ``field_height``: dimensions of the field
    - ``num_floors``: number of floors
    - ``floor_height`` and ``floor_spacing``: dimensions of a floor
    - ``lift_width`` and ``lift_height``: cabin dimensions
    - ``normal_speed`` and ``slow_speed``: movement speeds
    - ``door_speed_norm``: normalized door speed
    - ``lamp_radius``: radius of indicator lamps

    Returns
    -------
    dict
        Dictionary of processed configuration values.
    """
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