import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGraphicsScene, QGraphicsView, \
    QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox
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

class SensorLamp:
    def __init__(self, scene, x, y):
        self.rect = scene.addEllipse(x-LAMP_RADIUS, y-LAMP_RADIUS, LAMP_RADIUS*2, LAMP_RADIUS*2,
                                     brush=QBrush(QColor("gray")))
    def set_active(self, active):
        self.rect.setBrush(QBrush(QColor("red") if active else QColor("gray")))

class LiftView(QMainWindow):
    def __init__(self, lift_model):
        super().__init__()
        self.lift_model = lift_model

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

        # Лифт
        lift_y = self.lift_model.position - LIFT_HEIGHT/2
        self.lift_rect = self.scene.addRect((FIELD_WIDTH-LIFT_WIDTH)/2, lift_y, LIFT_WIDTH, LIFT_HEIGHT,
                                            brush=QBrush(QColor("blue")))

        # Таймер для анимации
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_view)
        self.moving_up = False
        self.moving_down = False

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

    def update_view(self):
        if self.moving_up:
            self.lift_model.move_up()
        if self.moving_down:
            self.lift_model.move_down()

        # Обновляем позицию лифта
        y = self.lift_model.position - LIFT_HEIGHT/2
        self.lift_rect.setRect((FIELD_WIDTH-LIFT_WIDTH)/2, y, LIFT_WIDTH, LIFT_HEIGHT)

        # Обновляем лампы
        active_sensors = self.lift_model.get_active_sensors()
        for floor_idx, lamp_row in enumerate(self.lamps):
            for i, lamp in enumerate(lamp_row):
                lamp.set_active(active_sensors[floor_idx][i])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    model = LiftModel(NUM_FLOORS, FIELD_HEIGHT, LIFT_HEIGHT, FLOOR_HEIGHT, FLOOR_SPACING)
    window = LiftView(model)
    window.show()
    sys.exit(app.exec_())
