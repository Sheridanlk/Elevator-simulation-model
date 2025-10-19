import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGraphicsScene, QGraphicsView,
    QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QMessageBox
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QBrush, QColor, QPainter

# Параметры поля
FIELD_WIDTH = 200
FIELD_HEIGHT = 600

NUM_FLOORS = 3
FLOOR_HEIGHT = 100
FLOOR_SPACING = 50

LIFT_WIDTH = 60
LIFT_HEIGHT = 80

NORMAL_SPEED = 2
SLOW_SPEED = 1

LAMP_RADIUS = 10

DOOR_SPEED_NORM = 0.03
DOOR_LEAF_RATIO = 0.45


class LiftModel:
    def __init__(self, num_floors, field_height, lift_height, floor_height, floor_spacing):
        self.num_floors = num_floors
        self.field_height = field_height
        self.lift_height = lift_height
        self.floor_height = floor_height
        self.floor_spacing = floor_spacing

        # Вычисляем одинаковые отступы сверху и снизу
        self.border_spacing = (field_height - (num_floors * floor_height) - floor_spacing * (num_floors - 1)) / 2

        # Изначально лифт по середине поля
        self.position = field_height / 2
        self.normal_speed = NORMAL_SPEED
        self.slow_speed = SLOW_SPEED
        self.current_speed = self.normal_speed

        # Датчики: верх, центр, низ каждого этажа
        self.sensors = []
        for floor in range(num_floors):
            base_y = self.border_spacing + floor * (floor_height + floor_spacing)
            top = base_y
            center = base_y + floor_height / 2
            bottom = base_y + floor_height
            self.sensors.append([top, center, bottom])

    def move_up(self):
        self.position -= self.current_speed
        self.position = max(self.position, self.lift_height / 2)

    def move_down(self):
        self.position += self.current_speed
        self.position = min(self.position, self.field_height - self.lift_height / 2)

    def toggle_slow(self, enabled):
        self.current_speed = self.slow_speed if enabled else self.normal_speed

    def get_active_sensors(self):
        lift_center = self.position
        active = []
        for floor_sensors in self.sensors:
            floor_active = []
            for y in floor_sensors:
                floor_active.append(abs(lift_center - y) <= self.current_speed*2)
            active.append(floor_active)
        return active

    def top_limit(self):
        return self.sensors[0][0]

    def bottom_limit(self):
        return self.sensors[self.num_floors - 1][2]

class DoorModel:
    def __init__(self, opening_w, speed_norm=DOOR_SPEED_NORM, leaf_ratio=DOOR_LEAF_RATIO):
        self.opening_w = opening_w
        self.leaf_ratio = leaf_ratio
        self.leaf_w = opening_w * leaf_ratio
        self.center_norm = 0.0      # старт: дверь закрыта (центр у левого косяка)
        self.speed_norm = speed_norm

    # движение (нормированное)
    def open_step(self):
        self.center_norm += self.speed_norm
        if self.center_norm > 1.0:
            self.center_norm = 1.0

    def close_step(self):
        self.center_norm -= self.speed_norm
        if self.center_norm < 0.0:
            self.center_norm = 0.0

    # геометрия в нормализованных координатах [0..1]
    def left_edge_norm(self):
        # левый край идёт от 0.0 (закрыто) до 1 - leaf_ratio
        return self.center_norm * (1.0 - self.leaf_ratio)

    def right_edge_norm(self):
        # правый край = левый + ширина полотна в норме
        return self.left_edge_norm() + self.leaf_ratio

    # в пикселях (для отрисовки)
    def get_leaf_left_px(self, cabin_left_px):
        left_px = cabin_left_px + self.left_edge_norm() * self.opening_w
        return left_px

    # ДАТЧИКИ ПО КРАЮ (с допуском от скорости)
    def get_edge_sensors_active(self):
        tol = self.speed_norm * 2
        left_ok  = abs(self.left_edge_norm() - 0.0) <= tol    # «закрыто» (левый датчик)
        right_ok = abs(self.right_edge_norm() - 1.0) <= tol    # «открыто до конца» (правый датчик)
        return left_ok, right_ok




class SensorLamp:
    def __init__(self, scene, x, y):
        self.rect = scene.addEllipse(x-LAMP_RADIUS, y-LAMP_RADIUS, LAMP_RADIUS*2, LAMP_RADIUS*2,
                                     brush=QBrush(QColor("gray")))
    def set_active(self, active):
        self.rect.setBrush(QBrush(QColor("red") if active else QColor("gray")))

    def set_pos(self, x, y):
        self.item.setRect(x - LAMP_RADIUS, y - LAMP_RADIUS, LAMP_RADIUS * 2, LAMP_RADIUS * 2)


class LiftView(QMainWindow):
    def __init__(self, lift_model: LiftModel, door_model: DoorModel):
        super().__init__()
        self.lift_model = lift_model
        self.door_model = door_model

        self.setWindowTitle("Lift Simulator PyQt5")
        self.showMaximized()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Игровое поле
        self.scene = QGraphicsScene(0, 0, FIELD_WIDTH, FIELD_HEIGHT)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setAlignment(Qt.AlignCenter | Qt.AlignCenter)
        layout.addWidget(self.view)

        # Интерфейс справа
        ui_layout = QVBoxLayout()
        layout.addLayout(ui_layout)

        self.up_btn = QPushButton("Up")
        self.down_btn = QPushButton("Down")
        ui_layout.addWidget(self.up_btn)
        ui_layout.addWidget(self.down_btn)
        self.up_btn.pressed.connect(self.start_up)
        self.up_btn.released.connect(self.stop)
        self.down_btn.pressed.connect(self.start_down)
        self.down_btn.released.connect(self.stop)

        self.slow_chk = QCheckBox("Slow Mode")
        self.slow_chk.stateChanged.connect(self.toggle_slow)
        ui_layout.addWidget(self.slow_chk)

        self.open_btn = QPushButton("Open door")
        self.close_btn = QPushButton("Close door")
        ui_layout.addWidget(self.open_btn)
        ui_layout.addWidget(self.close_btn)
        self.open_btn.pressed.connect(self.start_open)
        self.open_btn.released.connect(self.stop_door)
        self.close_btn.pressed.connect(self.start_close)
        self.close_btn.released.connect(self.stop_door)

        # Этажи и лампы
        self.floor_rects = []
        self.lamps = []
        for floor in range(self.lift_model.num_floors):
            base_y = self.lift_model.border_spacing + floor * (self.lift_model.floor_height + self.lift_model.floor_spacing)
            y1 = base_y
            rect = self.scene.addRect(20, y1, FIELD_WIDTH-40, self.lift_model.floor_height, brush=QBrush(QColor("lightgray")))
            self.floor_rects.append(rect)

            lamp_x = FIELD_WIDTH
            top_y = y1
            center_y = y1 + self.lift_model.floor_height/2
            bottom_y = y1 + self.lift_model.floor_height
            self.lamps.append([
                SensorLamp(self.scene, lamp_x, top_y),
                SensorLamp(self.scene, lamp_x, center_y),
                SensorLamp(self.scene, lamp_x, bottom_y)
            ])

        self.door_closed_lamp = SensorLamp(self.scene, self.cabin_x + LIFT_WIDTH + 20,
                                           self.cabin_y + LIFT_HEIGHT * 0.35)  # левый датчик (закрыто)
        self.door_open_lamp = SensorLamp(self.scene, self.cabin_x + LIFT_WIDTH + 20,
                                         self.cabin_y + LIFT_HEIGHT * 0.65)  # правый датчик (открыто)

        # Лифт
        lift_y = self.lift_model.position - LIFT_HEIGHT/2
        self.lift_rect = self.scene.addRect((FIELD_WIDTH-LIFT_WIDTH)/2, lift_y, LIFT_WIDTH, LIFT_HEIGHT,
                                            brush=QBrush(QColor("blue")))

        # Таймер для анимации
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_view)
        self.moving_up = False
        self.moving_down = False
        self.opening = False
        self.closing = False

        self.update_view()

    def start_up(self):
        self.moving_up = True
        self.timer.start(20)

    def start_down(self):
        self.moving_down = True
        self.timer.start(20)

    def stop(self):
        self.moving_up = False
        self.moving_down = False
        self.timer.stop()

    def toggle_slow(self, state):
        self.lift_model.toggle_slow(state == Qt.Checked)

    def start_open(self):
        self.opening = True
        self.closing = False
        self.timer.start(20)

    def start_close(self):
        self.closing = True
        self.opening = False
        self.timer.start(20)

    def stop_door(self):
        self.opening = False
        self.closing = False

    def show_emergency(self, text):
        self.stop()
        QMessageBox.critical(self, "Авария", text)

    def update_view(self):

        if self.moving_up:
            self.lift_model.move_up()
        if self.moving_down:
            self.lift_model.move_down()

        top_lim = self.lift_model.top_limit()
        bot_lim = self.lift_model.bottom_limit()

        if self.moving_up and self.lift_model.position <= top_lim:
            self.lift_model.position = top_lim
            self.update_cabin()
            self.update_lamps_only()
            self.show_emergency("Выход за верхний предел: сработал верхний аварийный датчик.")
            return

        if self.moving_down and self.lift_model.position >= bot_lim:
            self.lift_model.position = bot_lim
            self.update_cabin()
            self.update_lamps_only()
            self.show_emergency("Выход за нижний предел: сработал нижний аварийный датчик.")
            return

        if self.opening and self.door_model.center_norm < 1.0:
            self.door_model.open_step()
        if self.closing and self.door_model.center_norm > 0.0:
            self.door_model.close_step()

        self.update_cabin()
        self.update_lamps_only()

        if not (self.moving_up or self.moving_down or self.opening or self.closing):
            self.timer.stop()

    def update_cabin(self):
        # кабина
        self.cabin_x = (FIELD_WIDTH - LIFT_WIDTH) / 2
        self.cabin_y = self.lift_model.position - LIFT_HEIGHT / 2
        self.cabin_item.setRect(self.cabin_x, self.cabin_y, LIFT_WIDTH, LIFT_HEIGHT)

        # дверь: левый край по нормализованной геометрии
        door_left_px = self.door_model.get_leaf_left_px(self.cabin_x)
        self.door_leaf_w = LIFT_WIDTH * DOOR_LEAF_RATIO
        self.door_item.setRect(door_left_px, self.cabin_y, self.door_leaf_w, LIFT_HEIGHT)

        # лампы двери «едут» вместе с кабиной
        lamp_x = self.cabin_x + LIFT_WIDTH + 20
        self.door_closed_lamp.set_pos(lamp_x, self.cabin_y + LIFT_HEIGHT * 0.35)
        self.door_open_lamp.set_pos(lamp_x, self.cabin_y + LIFT_HEIGHT * 0.65)

    def update_lamps_only(self):
        active_sensors = self.lift_model.get_active_sensors()
        for floor_idx, lamp_row in enumerate(self.lamps):
            for i, lamp in enumerate(lamp_row):
                lamp.set_active(active_sensors[floor_idx][i])
        # дверь: датчики по КРАЯМ (левый=закрыто, правый=открыто)
        left_ok, right_ok = self.door_model.get_edge_sensors_active()
        self.door_closed_lamp.set_active(left_ok)
        self.door_open_lamp.set_active(right_ok)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    lift = LiftModel(NUM_FLOORS, FIELD_HEIGHT, LIFT_HEIGHT, FLOOR_HEIGHT, FLOOR_SPACING)
    door = DoorModel(opening_w=LIFT_WIDTH, speed_norm=DOOR_SPEED_NORM, leaf_ratio=DOOR_LEAF_RATIO)
    window = LiftView(lift, door)
    window.show()
    sys.exit(app.exec_())
