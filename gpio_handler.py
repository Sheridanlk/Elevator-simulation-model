try:
    from gpiozero import DigitalInputDevice, DigitalOutputDevice
    from gpiozero.pins.mock import MockFactory
    IS_RPI = True
except (ImportError, RuntimeError):
    IS_RPI = False
    print("GPIO не найден. Работаем в режиме симуляции.")


class GPIOHandler:
    def __init__(self):
        self.in_config = {
            "up": 17, "down": 27,
            "open": 22, "close": 23,
            "low_speed": 24,

            "l_c1": 2, "l_c2": 3, "l_c3": 4,  # Лампы кабин
            "l_f1": 10, "l_f2": 9, "l_f3": 11  # Лампы этажей
        }

        self.out_config = {
            "f1_down": 5, "f1_mid": 6, "f1_up": 13,
            "f2_down": 19, "f2_mid": 26, "f2_up": 16,
            "f3_down": 20, "f3_mid": 21, "f3_up": 12,

            "vko": 14, "vkz": 15,

            "btn_c1": 18, "btn_c2": 25, "btn_c3": 8,
            "btn_f1": 7, "btn_f2": 1, "btn_f3": 0
        }

        self.inputs = {}
        self.outputs = {}

        if IS_RPI:
            # Инициализация реальных пинов
            for name, pin in self.in_config.items():
                # pull_up=False эквивалентно PUD_DOWN
                self.inputs[name] = DigitalInputDevice(pin, pull_up=False)

            for name, pin in self.out_config.items():
                self.outputs[name] = DigitalOutputDevice(pin, initial_value=False)

    def read_inputs(self):
        cmds = {}
        for name in self.in_config:
            if IS_RPI and name in self.inputs:
                # .is_active возвращает True, если на пине High (3.3V)
                cmds[name] = self.inputs[name].is_active
            else:
                cmds[name] = False
        return cmds

    def write_outputs(self, sensor_states):
        if not IS_RPI:
            return

        for name, state in sensor_states.items():
            if name in self.outputs:
                if state:
                    self.outputs[name].on()  # Подать High
                else:
                    self.outputs[name].off()  # Подать Low