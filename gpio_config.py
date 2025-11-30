import os
import yaml
from typing import Any, Dict


def _load_raw_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_gpio_config() -> Dict[str, Any]:
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
        "cabin_button_lamps": inputs.get("cabin_button_lamps", []),
        "floor_button_lamps": inputs.get("floor_button_lamps", []),
    }
    # Outputs
    outputs = raw.get("outputs", {})
    cfg_outputs: Dict[str, Any] = {}
    cfg_outputs["floor_sensors"] = outputs.get("floor_sensors", [])
    cfg_outputs["door_sensors"] = outputs.get("door_sensors", [])
    cfg_outputs["cabin_buttons"] = outputs.get("cabin_buttons", [])
    cfg_outputs["floor_buttons"] = outputs.get("floor_buttons", [])
    cfg["outputs"] = cfg_outputs
    return cfg


GPIO_CONFIG: Dict[str, Any] = load_gpio_config()

__all__ = ["GPIO_CONFIG", "load_gpio_config"]