"""
GPIO configuration loader for the Raspberry Pi lift simulation.

This module reads ``gpio_config.yaml`` from the project directory and
exposes a single dictionary called ``GPIO_CONFIG``.  The YAML file
defines whether GPIO access is enabled and maps logical lift functions
to Raspberry Pi GPIO pin numbers.  The pins are specified using the
BCM numbering scheme.

Example usage::

    from gpio_config import GPIO_CONFIG
    if GPIO_CONFIG['enable']:
        print(GPIO_CONFIG['inputs']['up'])

The configuration structure mirrors the YAML file:

```
enable: <bool>
inputs:
  up: <pin>
  down: <pin>
  open_door: <pin>
  close_door: <pin>
  slow_mode: <pin>
outputs:
  floor_sensors: [[pin,pin,pin], ...]
  cabin_buttons: [pin, pin, pin]
  floor_buttons: [pin, pin, pin]
```
"""

import os
import yaml
from typing import Any, Dict


def _load_raw_config(path: str) -> Dict[str, Any]:
    """Load and return the raw GPIO YAML configuration."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_gpio_config() -> Dict[str, Any]:
    """Load the GPIO configuration from ``gpio_config.yaml``.

    Returns
    -------
    dict
        Parsed configuration dictionary with keys ``enable``, ``inputs``
        and ``outputs``.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(current_dir, "gpio_config.yaml")
    raw = _load_raw_config(yaml_path)
    cfg: Dict[str, Any] = {}
    # Enable flag
    cfg["enable"] = bool(raw.get("enable", False))
    # Inputs
    inputs = raw.get("inputs", {})
    cfg["inputs"] = {
        "up": inputs.get("up"),
        "down": inputs.get("down"),
        "open_door": inputs.get("open_door"),
        "close_door": inputs.get("close_door"),
        "slow_mode": inputs.get("slow_mode"),
    }
    # Outputs
    outputs = raw.get("outputs", {})
    cfg_outputs: Dict[str, Any] = {}
    cfg_outputs["floor_sensors"] = outputs.get("floor_sensors", [])
    cfg_outputs["cabin_buttons"] = outputs.get("cabin_buttons", [])
    cfg_outputs["floor_buttons"] = outputs.get("floor_buttons", [])
    cfg["outputs"] = cfg_outputs
    return cfg


GPIO_CONFIG: Dict[str, Any] = load_gpio_config()

__all__ = ["GPIO_CONFIG", "load_gpio_config"]