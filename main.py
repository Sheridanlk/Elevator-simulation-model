import sys
from PyQt5.QtWidgets import QApplication

from config import CONFIG
from models import LiftModel, DoorModel
from views import LiftView
from gpio_config import GPIO_CONFIG
from gpio_handler import GPIOHandler


def main() -> None:
    app = QApplication(sys.argv)
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
    gpio_handler = GPIOHandler(GPIO_CONFIG)
    try:
        gpio_handler.setup()
    except Exception:
        pass
    win = LiftView(lift, door, CONFIG, gpio_handler)
    win.show()
    try:
        sys.exit(app.exec_())
    finally:
        try:
            gpio_handler.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    main()