import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGraphicsScene, QGraphicsView,
    QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QMessageBox, QGraphicsRectItem
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QBrush, QColor, QPainter

k = 2
# ---- сценография ----
FIELD_WIDTH = 400 * k
FIELD_HEIGHT = 600 * k

NUM_FLOORS = 3
FLOOR_HEIGHT = 100 * k
FLOOR_SPACING = 50 * k

# Кабина
LIFT_WIDTH = 60 * k
LIFT_HEIGHT = 80 * k

# Скорости
NORMAL_SPEED = 2 * k
SLOW_SPEED = 1 * k

# Дверь
DOOR_SPEED_NORM = 0.03    # шаг по normalized позиции за тик

# Лампы
LAMP_RADIUS = 10 * k


# =================== МОДЕЛИ ===================

class LiftModel:
    """Вертикальная логика лифта (этажи, скорость, позиция по Y)"""
    def __init__(self, num_floors, field_height, lift_height, floor_height, floor_spacing):
        self.num_floors = num_floors
        self.field_height = field_height
        self.lift_height = lift_height
        self.floor_height = floor_height
        self.floor_spacing = floor_spacing

        self.border_spacing = (field_height - (num_floors * floor_height) - floor_spacing * (num_floors - 1)) / 2

        # позиция = СЕРЕДИНА кабины (ось Y сверху-вниз)
        self.position = field_height / 2
        self.normal_speed = NORMAL_SPEED
        self.slow_speed = SLOW_SPEED
        self.current_speed = self.normal_speed

        # датчики этажей (y-координаты: верх, центр, низ для каждого этажа)
        self.sensors = []
        for floor in range(num_floors):
            base_y = self.border_spacing + floor * (floor_height + floor_spacing)  # верх этажа
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

    def get_active_floor_sensors(self):
        """true/false по 3 датчика на этаж: активен, когда СЕРЕДИНА кабины проходит уровень датчика"""
        lift_center = self.position
        tol = self.current_speed * 2
        active = []
        for floor_sensors in self.sensors:
            active.append([abs(lift_center - y) <= tol for y in floor_sensors])
        return active

    def top_limit(self):
        return self.sensors[0][0]

    def bottom_limit(self):
        return self.sensors[self.num_floors - 1][2]

    def is_on_floor_center(self) -> bool:
        # центральный датчик (второй в тройке top/center/bottom) активен на любом этаже?
        active = self.get_active_floor_sensors()
        return any(row[1] for row in active)


class DoorModel:
    """
    Одна створка, едет ВПРАВО.
    Работаем с НОРМАЛИЗОВАННЫМ левым краем: left_norm ∈ [0..1]
      0.0 -> левый край полотна на левом косяке (дверь закрыта, проём перекрыт)
      1.0 -> левый край полотна на правом косяке (полотно полностью уехало вправо за пределы проёма)
    """
    def __init__(self, opening_w, speed_norm=DOOR_SPEED_NORM):
        self.opening_w = opening_w             # ширина проёма (обычно = LIFT_WIDTH)
        self.leaf_w = opening_w                # ширина полотна = ширине проёма
        self.left_norm = 0.0                   # старт: дверь закрыта
        self.speed_norm = speed_norm

    def open_step(self):
        self.left_norm += self.speed_norm
        if self.left_norm > 1.0:
            self.left_norm = 1.0

    def close_step(self):
        self.left_norm -= self.speed_norm
        if self.left_norm < 0.0:
            self.left_norm = 0.0

    def get_leaf_left_px(self, cabin_left_px: float) -> float:
        """Левый край полотна в пикселях"""
        return cabin_left_px + self.left_norm * self.opening_w

    def get_edge_sensors_active(self):
        """Датчики по краю: левый (закрыто) и правый (полностью открыто)"""
        tol = self.speed_norm * 2
        left_ok  = abs(self.left_norm - 0.0) <= tol   # «закрыто»
        right_ok = abs(self.left_norm - 1.0) <= tol   # «открыто»
        return left_ok, right_ok


# =================== ВСПОМОГАТЕЛЬНАЯ ЛАМПА ===================

class SensorLamp:
    def __init__(self, scene, x, y):
        self.item = scene.addEllipse(x - LAMP_RADIUS, y - LAMP_RADIUS,
                                     LAMP_RADIUS * 2, LAMP_RADIUS * 2,
                                     brush=QBrush(QColor("gray")))
    def set_active(self, active: bool):
        self.item.setBrush(QBrush(QColor("red") if active else QColor("gray")))
    def set_pos(self, x, y):
        self.item.setRect(x - LAMP_RADIUS, y - LAMP_RADIUS, LAMP_RADIUS * 2, LAMP_RADIUS * 2)


# =================== VIEW / UI ===================

class LiftView(QMainWindow):
    def __init__(self, lift_model: LiftModel, door_model: DoorModel):
        super().__init__()
        self.lift_model = lift_model
        self.door_model = door_model

        self.setWindowTitle("Lift Simulator PyQt5 — fixed timers & lamps & door")


        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # сцена/вид
        self.scene = QGraphicsScene(0, 0, FIELD_WIDTH, FIELD_HEIGHT)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)

        # ОСТАВЛЯЮ КАК ПРОСИЛ: центрирование
        self.view.setAlignment(Qt.AlignCenter | Qt.AlignCenter)

        layout.addWidget(self.view)

        # панель управления справа
        ui_layout = QVBoxLayout()
        ui_layout.setContentsMargins(6, 6, 6, 6)
        ui_layout.setSpacing(8)
        layout.addLayout(ui_layout)

        # движение лифта
        move_row = QVBoxLayout()
        move_row.setSpacing(6)

        self.up_btn = QPushButton("Up")
        self.down_btn = QPushButton("Down")

        move_row.addWidget(self.up_btn)
        move_row.addWidget(self.down_btn)
        ui_layout.addLayout(move_row)

        self.up_btn.pressed.connect(self.start_up)
        self.up_btn.released.connect(self.stop_move)
        self.down_btn.pressed.connect(self.start_down)
        self.down_btn.released.connect(self.stop_move)

        # slow mode
        self.slow_chk = QCheckBox("Slow Mode")
        self.slow_chk.stateChanged.connect(self.toggle_slow)
        ui_layout.addWidget(self.slow_chk)

        # дверь
        door_row = QVBoxLayout()
        door_row.setSpacing(6)

        self.open_btn = QPushButton("Open door")
        self.close_btn = QPushButton("Close door")

        door_row.addWidget(self.open_btn)
        door_row.addWidget(self.close_btn)
        ui_layout.addLayout(door_row)

        self.open_btn.pressed.connect(self.start_open)
        self.open_btn.released.connect(self.stop_door)
        self.close_btn.pressed.connect(self.start_close)
        self.close_btn.released.connect(self.stop_door)

        # этажи
        self.floor_rects = []
        for floor in range(self.lift_model.num_floors):
            base_y = self.lift_model.border_spacing + floor * (self.lift_model.floor_height + self.lift_model.floor_spacing)
            rect = self.scene.addRect(20, base_y, FIELD_WIDTH - 40, self.lift_model.floor_height,
                                      brush=QBrush(QColor("lightgray")))
            self.floor_rects.append(rect)

        # кабина
        self.cabin_x = (FIELD_WIDTH - LIFT_WIDTH) / 2
        self.cabin_y = self.lift_model.position - LIFT_HEIGHT / 2
        self.cabin_item = self.scene.addRect(self.cabin_x, self.cabin_y, LIFT_WIDTH, LIFT_HEIGHT,
                                             brush=QBrush(QColor("#2E68FF")))

        # дверь — статическая форма + меняем только позицию setPos (стабильнее)
        self.door_item = QGraphicsRectItem(0, 0, LIFT_WIDTH, LIFT_HEIGHT)
        self.door_item.setBrush(QBrush(QColor("#5C7AEA")))
        self.scene.addItem(self.door_item)
        door_left = self.door_model.get_leaf_left_px(self.cabin_x)
        self.door_item.setPos(door_left, self.cabin_y)

        # лампы этажей (3 на этаж), СДВИГАЕМ ВНУТРЬ СЦЕНЫ
        self.floor_lamps = []
        lamp_x = FIELD_WIDTH - LAMP_RADIUS - 2
        for floor in range(self.lift_model.num_floors):
            base_y = self.lift_model.border_spacing + floor * (self.lift_model.floor_height + self.lift_model.floor_spacing)
            top_y = base_y
            center_y = base_y + self.lift_model.floor_height / 2
            bottom_y = base_y + self.lift_model.floor_height
            self.floor_lamps.append([
                SensorLamp(self.scene, lamp_x, top_y),
                SensorLamp(self.scene, lamp_x, center_y),
                SensorLamp(self.scene, lamp_x, bottom_y)
            ])

        # лампы двери — НАД КАБИНОЙ, ездят вместе с ней
        lamp_y = self.cabin_y - 14
        self.door_closed_lamp = SensorLamp(self.scene, self.cabin_x + LIFT_WIDTH * 0.35, lamp_y)  # «закрыто»
        self.door_open_lamp   = SensorLamp(self.scene, self.cabin_x + LIFT_WIDTH * 0.65, lamp_y)  # «открыто»

        # таймер
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.moving_up = False
        self.moving_down = False
        self.opening = False
        self.closing = False

        self.update_all()
        self.showMaximized()

    # --- управление лифтом ---
    def start_up(self):
        left_ok, _ = self.door_model.get_edge_sensors_active()
        if not left_ok:
            self.show_emergency("Запрещено движение: дверь не закрыта.")
            return
        self.moving_up = True
        if not self.timer.isActive():
            self.timer.start(20)

    def start_down(self):
        left_ok, _ = self.door_model.get_edge_sensors_active()
        if not left_ok:
            self.show_emergency("Запрещено движение: дверь не закрыта.")
            return
        self.moving_down = True
        if not self.timer.isActive():
            self.timer.start(20)

    def stop_move(self):
        self.moving_up = False
        self.moving_down = False
        # НЕ останавливаем таймер здесь, его выключим только если ничто не движется (в tick())

    def toggle_slow(self, state):
        self.lift_model.toggle_slow(state == Qt.Checked)

    # --- управление дверью ---
    def start_open(self):
        # запрещаем, если лифт в движении
        if self.moving_up or self.moving_down:
            self.show_emergency("Запрещено открывать дверь во время движения!")
            return
        # запрещаем, если не стоим точно на этаже (центральный датчик не активен)
        if not self.lift_model.is_on_floor_center():
            self.show_emergency("Запрещено открывать дверь: кабина не на этаже!")
            return
        self.opening = True
        self.closing = False
        if not self.timer.isActive():
            self.timer.start(20)

    def start_close(self):
        self.closing = True
        self.opening = False
        if not self.timer.isActive():
            self.timer.start(20)

    def stop_door(self):
        self.opening = False
        self.closing = False

    # --- аварийное окно (верх/низ этажей) ---
    def show_emergency(self, text):
        self.moving_up = self.moving_down = self.opening = self.closing = False
        self.timer.stop()
        QMessageBox.critical(self, "Авария", text)

    # --- главный тик ---
    def tick(self):
        try:
            prev_pos = self.lift_model.position

            # 1) вертикаль
            if self.moving_up:
                self.lift_model.move_up()
            if self.moving_down:
                self.lift_model.move_down()

            # 2) предельные датчики по этажам (верх/низ)
            top_lim = self.lift_model.top_limit()
            bot_lim = self.lift_model.bottom_limit()
            if self.moving_up and self.lift_model.position <= top_lim:
                self.lift_model.position = top_lim
                self.update_geometry()
                self.update_lamps()
                self.show_emergency("Выход за верхний предел: сработал верхний аварийный датчик.")
                return
            if self.moving_down and self.lift_model.position >= bot_lim:
                self.lift_model.position = bot_lim
                self.update_geometry()
                self.update_lamps()
                self.show_emergency("Выход за нижний предел: сработал нижний аварийный датчик.")
                return

            # 3) горизонталь (дверь)
            if self.opening and self.door_model.left_norm < 1.0:
                self.door_model.open_step()
            if self.closing and self.door_model.left_norm > 0.0:
                self.door_model.close_step()




            # 4) перерисовка
            self.update_geometry()
            self.update_lamps()

            # 5) автостоп таймера — только если вообще ничего не движется
            if not (self.moving_up or self.moving_down or self.opening or self.closing):
                self.timer.stop()

        except Exception as e:
            self.timer.stop()
            QMessageBox.critical(self, "Ошибка", f"{type(e).__name__}: {e}")

    def update_geometry(self):
        # кабина
        self.cabin_x = (FIELD_WIDTH - LIFT_WIDTH) / 2
        self.cabin_y = self.lift_model.position - LIFT_HEIGHT / 2
        self.cabin_item.setRect(self.cabin_x, self.cabin_y, LIFT_WIDTH, LIFT_HEIGHT)

        # дверь: двигаем только позицию (форма постоянная)
        door_left_px = self.door_model.get_leaf_left_px(self.cabin_x)
        self.door_item.setPos(door_left_px, self.cabin_y)

        # лампы двери — над кабиной
        lamp_y = self.cabin_y - 14
        self.door_closed_lamp.set_pos(self.cabin_x + LIFT_WIDTH * 0.35, lamp_y)
        self.door_open_lamp.set_pos(self.cabin_x + LIFT_WIDTH * 0.65, lamp_y)

    def update_lamps(self):
        # этажи
        active_floor = self.lift_model.get_active_floor_sensors()
        for floor_idx, row in enumerate(self.floor_lamps):
            for i, lamp in enumerate(row):
                lamp.set_active(active_floor[floor_idx][i])

        # дверь: датчики по КРАЯМ (левый=закрыто, правый=открыто)
        left_ok, right_ok = self.door_model.get_edge_sensors_active()
        self.door_closed_lamp.set_active(left_ok)
        self.door_open_lamp.set_active(right_ok)

    def update_all(self):
        self.update_geometry()
        self.update_lamps()


# =================== запуск ===================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    lift = LiftModel(NUM_FLOORS, FIELD_HEIGHT, LIFT_HEIGHT, FLOOR_HEIGHT, FLOOR_SPACING)
    door = DoorModel(opening_w=LIFT_WIDTH, speed_norm=DOOR_SPEED_NORM)
    win = LiftView(lift, door)
    win.show()
    sys.exit(app.exec_())
