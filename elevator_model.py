# elevator_model.py
class ElevatorModel:
    def __init__(self):
        self.NORMAL_SPEED = 1
        self.SLOW_SPEED = 0.5
        self.DOOR_SPEED = 0.5

        self.position = 0.0
        self.speed = 0.0
        self.door_pos = 0.0

        self.FLOORS = {1: 0.0, 2: 3, 3: 6}
        self.OFFSET = 0.8
        self.SENSOR_TYPES = [
            ("up", self.OFFSET),
            ("mid", self.OFFSET * 0),
            ("down", self.OFFSET * -1)
        ]
        self.SENSOR_WIDTH = 0.075

        self.CABIN_HEIGHT = 1.5
        self.SAFETY_MARGIN = 0.5
        self.MIN_POS = min(self.FLOORS.values()) - (self.CABIN_HEIGHT + self.SAFETY_MARGIN)
        self.MAX_POS = max(self.FLOORS.values()) + (self.CABIN_HEIGHT + self.SAFETY_MARGIN)

    def update(self, dt, commands):
        if commands.get('up'):
            target_v = self.SLOW_SPEED if commands.get('low_speed') else self.NORMAL_SPEED
            self.speed = target_v
        elif commands.get('down'):
            target_v = self.SLOW_SPEED if commands.get('low_speed') else self.NORMAL_SPEED
            self.speed = -target_v
        else:
            self.speed = 0

        self.position += self.speed * dt

        # Ограничение поля
        if self.position < self.MIN_POS:
            self.position = self.MIN_POS
            self.speed = 0
        elif self.position > self.MAX_POS:
            self.position = self.MAX_POS
            self.speed = 0

        # Двери
        if commands.get('open'):
            self.door_pos = min(1.0, self.door_pos + self.DOOR_SPEED * dt)
        elif commands.get('close'):
            self.door_pos = max(0.0, self.door_pos - self.DOOR_SPEED * dt)

    def get_sensors(self):
        s = {}
        # Этажей
        for f, h in self.FLOORS.items():
            s[f"f{f}_mid"] = abs(self.position - h) < self.SENSOR_WIDTH
            s[f"f{f}_up"] = abs(self.position - (h + self.OFFSET)) < self.SENSOR_WIDTH
            s[f"f{f}_down"] = abs(self.position - (h - self.OFFSET)) < self.SENSOR_WIDTH

        # Дверей
        s["vko"] = self.door_pos >= 1
        s["vkz"] = self.door_pos <= 0
        return s

    def get_faults(self):
        faults = []

        sensors = self.get_sensors()
        top_sensor_level = max(self.FLOORS.values()) + self.OFFSET
        bottom_sensor_level = min(self.FLOORS.values()) - self.OFFSET

        if abs(self.speed) > 0.0 and self.door_pos > 0.0:
            faults.append("АВАРИЯ: ДВИЖЕНИЕ С ОТКРЫТОЙ ДВЕРЬЮ")

        if sensors.get("f1_down") or self.position < bottom_sensor_level:
            faults.append("АВАРИЯ: ВЫХОД ЗА НИЖНИЙ ПРЕДЕЛ")

        if sensors.get("f3_up") or self.position > top_sensor_level:
            faults.append("АВАРИЯ: ВЫХОД ЗА ВЕРХНИЙ ПРЕДЕЛ")

        if self.door_pos > 0.0 and not(sensors.get("f1_mid") or sensors.get("f2_mid") or sensors.get("f3_mid")):
            faults.append("АВАРИЯ: ОТКРЫТИЕ ДВЕРИ ВНЕ ЭТАЖА")

        return faults