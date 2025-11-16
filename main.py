"""
Entry point for the lift simulation.

This script loads configuration from ``config.yaml``, constructs the
data models for the lift and door, instantiates the PyQt GUI, and
starts the application event loop.  The simulation can be run by
executing this file directly with Python::

    python main.py

The functionality remains identical to the original monolithic
implementation, but the code is now organised into separate modules
for configuration, models and views.
"""

import sys
from PyQt5.QtWidgets import QApplication

from config import CONFIG
from models import LiftModel, DoorModel
from views import LiftView
from gpio_config import GPIO_CONFIG
from gpio_handler import GPIOHandler


def main() -> None:
    """Start the lift simulation application."""
    app = QApplication(sys.argv)
    # Instantiate models with parameters from the configuration
    lift = LiftModel(
        CONFIG["num_floors"],
        CONFIG["field_height"],
        CONFIG["lift_height"],
        CONFIG["floor_height"],
        CONFIG["floor_spacing"],
        CONFIG["normal_speed"],
        CONFIG["slow_speed"],
    )
    door = DoorModel(
        opening_w=CONFIG["lift_width"],
        speed_norm=CONFIG["door_speed_norm"],
    )
    # Instantiate GPIO handler and set up pins
    gpio_handler = GPIOHandler(GPIO_CONFIG)
    try:
        gpio_handler.setup()
    except Exception:
        pass
    win = LiftView(lift, door, CONFIG, gpio_handler)
    win.show()
    # Run the Qt event loop and clean up GPIO on exit
    try:
        sys.exit(app.exec_())
    finally:
        try:
            gpio_handler.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    main()