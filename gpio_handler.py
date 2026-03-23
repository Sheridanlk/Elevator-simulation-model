try:
    import RPi.GPIO as GPIO
    IS_RPI = True
except (ImportError, RuntimeError):
    IS_RPI = False
    print("GPIO не найден. Работаем в режиме симуляции.")


class GPIOHandler:
    def __init__(self):
        self.IN_PINS = {
            "up": 17, "down": 27,
            "open": 22, "close": 23,
            "low_speed": 24,

            "l_c1": 2, "l_c2": 3, "l_c3": 4,  # Лампы кабин
            "l_f1": 10, "l_f2": 9, "l_f3": 11  # Лампы этажей
        }

        self.OUT_PINS = {
            "f1_down": 5, "f1_mid": 6, "f1_up": 13,
            "f2_down": 19, "f2_mid": 26, "f2_up": 16,
            "f3_down": 20, "f3_mid": 21, "f3_up": 12,

            "vko": 14, "vkz": 15,

            "btn_c1": 18, "btn_c2": 25, "btn_c3": 8,
            "btn_f1": 7, "btn_f2": 1, "btn_f3": 0
        }

        if IS_RPI:
            GPIO.setmode(GPIO.BCM)
            for pin in self.IN_PINS.values():
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            for pin in self.OUT_PINS.values():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)

    def read_inputs(self):
        cmds = {}
        for name, pin in self.IN_PINS.items():
            cmds[name] = GPIO.input(pin) if IS_RPI else False
        return cmds

    def write_outputs(self, sensor_states):
        if not IS_RPI: return
        for name, state in sensor_states.items():
            if name in self.OUT_PINS:
                GPIO.output(self.OUT_PINS[name], GPIO.HIGH if state else GPIO.LOW)