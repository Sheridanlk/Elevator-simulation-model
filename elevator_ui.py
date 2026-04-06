from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsItemGroup, \
    QFrame, QVBoxLayout, QLabel, QPushButton, QWidget, QGraphicsTextItem, QGraphicsPathItem
from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QTimer, QRectF
from PyQt6.QtGui import QPainter, QPen, QFont, QPainterPath
from PyQt6.QtGui import QColor, QBrush



class ElevatorCabin(QGraphicsItemGroup):
    def __init__(self):
        super().__init__()

        # Кабина
        # self.body = QGraphicsRectItem(0, 0, 220, 230)
        # self.body.setBrush(QBrush(QColor("#34495e")))
        self.body = QGraphicsSvgItem("Assets/cabin.svg")
        self.addToGroup(self.body)

        # Рамка для клиппинга дверей
        self.door_viewport = QGraphicsRectItem(36, 20, 148, 190, self)
        self.door_viewport.setPen(QPen(Qt.PenStyle.NoPen))
        self.door_viewport.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.door_viewport.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemClipsChildrenToShape)

        # Левая и правая двери
        # self.door_l = QGraphicsRectItem(35, 20, 75, 190)
        # self.door_l.setBrush(QBrush(QColor("#bdc3c7")))
        self.left_door_container = QGraphicsItemGroup(self.door_viewport)
        self.left_door_container.setPos(35, 20)  # Ставим контейнер там, где должна быть дверь
        self.door_l = QGraphicsSvgItem("Assets/door.svg")
        self.door_l.setParentItem(self.left_door_container)

        # self.door_r = QGraphicsRectItem(110, 20, 75, 190)
        # self.door_r.setBrush(QBrush(QColor("#bdc3c7")))
        self.right_door_container = QGraphicsItemGroup(self.door_viewport)
        self.right_door_container.setPos(110, 20)
        self.door_r = QGraphicsSvgItem("Assets/door.svg")
        self.door_r.setParentItem(self.right_door_container)

        # Датчики дверей ВКО/ВКЗ

        self.led_vko = Sensor("ВКО", width=35, height=18)
        self.led_vko.setPos(70, 0)
        self.addToGroup(self.led_vko)

        self.led_vkz = Sensor("ВКЗ", width=35, height=18)
        self.led_vkz.setPos(115, 0)
        self.addToGroup(self.led_vkz)



    def set_door_position(self, value):
        offset = value * 75  # Ширина сдвига
        self.door_l.setPos(-offset, 0)
        self.door_r.setPos(offset, 0)

    def set_door_leds(self, vko, vkz):
        self.led_vko.set_active(vko)
        self.led_vkz.set_active(vkz)


class Sensor(QGraphicsItemGroup):
    def __init__(self, text, width=40, height=25):
        super().__init__()

        # Цвета (базовые)
        self.off_color = QColor(107, 121, 16)  # Оливковый
        self.on_color = QColor(173, 255, 47)  # Салатовый
        self.black = QColor(0, 0, 0)

        # 1. Рисуем подложку (скругленный прямоугольник)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, width, height), 7, 7)

        self.bg = QGraphicsPathItem(path)
        self.bg.setPen(QPen(self.black, 2))
        self.bg.setBrush(QBrush(self.off_color))
        self.addToGroup(self.bg)

        # 2. Добавляем текст
        self.label = QGraphicsTextItem(text)
        self.label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.label.setDefaultTextColor(self.black)

        # Центрируем текст внутри прямоугольника
        t_rect = self.label.boundingRect()
        self.label.setPos((width - t_rect.width()) / 2, (height - t_rect.height()) / 2)
        self.addToGroup(self.label)

    def set_active(self, is_active):
        color = self.on_color if is_active else self.off_color
        self.bg.setBrush(QBrush(color))


class ElevatorView(QGraphicsView):
    def __init__(self, model):
        super().__init__()
        self.model = model
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Параметры отрисовки
        self.cabin_height_px = 230
        self.scale_m = 300.0/3.0
        self.ground_y = 1010 - self.cabin_height_px/2

        # Создаем объекты
        self._init_shaft()
        self._init_floor_sensors()
        self._init_floor_panels()

        self.cabin = ElevatorCabin()
        self.scene.addItem(self.cabin)

    def _init_shaft(self):

        self.shaft_svg = QGraphicsSvgItem("Assets/vent3.svg")
        self.shaft_svg.setZValue(-1)
        self.shaft_svg.setPos(0, 0)
        self.scene.addItem(self.shaft_svg)

        svg_rect = self.shaft_svg.boundingRect()
        self.scene.setSceneRect(0, 0, svg_rect.width(), svg_rect.height())

    def _init_floor_sensors(self):
        self.floor_leds = {}

        SENSOR_X_LINE = 265

        LABEL_WIDTH = 40
        LABEL_HEIGHT = 25

        for f, h in self.model.FLOORS.items():
            for s_type, offset in self.model.SENSOR_TYPES:
                # Расчет Y (инвертируем, так как в Qt Y растет вниз)
                y_pos = self.ground_y - (h + offset) * self.scale_m - (LABEL_HEIGHT / 2)
                x_pos = SENSOR_X_LINE - LABEL_WIDTH/2
                names = {
                    "up": "В", "mid": "С", "down": "Н"
                }
                sensor = Sensor(f"{f}{names[s_type]}")
                sensor.setPos(x_pos, y_pos)
                self.scene.addItem(sensor)
                self.floor_leds[f"f{f}_{s_type}"] = sensor
    def _init_floor_panels(self):
        PANEL_X_LINE = 800
        self.floor_call_panels = {}

        for floor_num, y_mid in self.model.FLOORS.items():
            panel = FloorPanel(floor_num)
            self.scene.addItem(panel)

            y_pos = self.ground_y - y_mid * self.scale_m - 50
            x_pos = PANEL_X_LINE + 20

            panel.setPos(x_pos, y_pos)

            self.floor_call_panels[floor_num] = panel

    def update_ui(self, sensors):
        # Позиция кабины
        center_y_px = self.ground_y - (self.model.position * self.scale_m)
        draw_y = center_y_px - (self.cabin_height_px / 2)
        self.cabin.setPos(400-110, draw_y)

        # Состояние дверей
        self.cabin.set_door_position(self.model.door_pos)
        self.cabin.set_door_leds(sensors["vko"], sensors["vkz"])

        # Состояние этажных датчиков
        for key, led in self.floor_leds.items():
            active = sensors.get(key, False)
            led.set_active(active)

    def resizeEvent(self, event):
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)



class Toast(QFrame):
    def __init__(self, parent, text, is_error=True):
        super().__init__(parent)
        self.setFixedSize(280, 45)

        bg_color = "#c0392b" if is_error else "#2c3e50"

        self.setStyleSheet(f"""
                    QFrame {{
                        background-color: {bg_color};
                        color: white;
                        border-radius: 5px;
                        border: 2px solid rgba(255,255,255,0.2);
                    }}
                    QLabel {{ border: none; font-weight: bold; font-size: 11px; }}
                """)

        layout = QVBoxLayout(self)
        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        # Жесткая позиция: справа снизу с небольшим отступом
        margin = 20
        # x = parent.width() - self.width() - margin
        x = margin
        y = parent.height() - self.height() - margin
        self.move(x, y)
        self.show()


class ElevatorControlBlock(QWidget):
    def __init__(self, floor_num):
        super().__init__()
        layout = QVBoxLayout()
        layout.setSpacing(8)  # Расстояние между лампой и кнопкой
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Лампочка (Индикатор, которым управляет ПЛК)
        self.lamp = QLabel()
        self.lamp.setFixedSize(35, 15)
        # Темно-зеленый (выключена) по умолчанию
        self.lamp.setStyleSheet("background-color: #004400; border-radius: 6px; border: 1px solid #333;")

        # 2. Кнопка приказа
        self.btn = QPushButton()
        self.btn.setFixedSize(55, 55)
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: #666666; 
                border: 3px solid #444444;
                border-radius: 4px;
            }
            QPushButton:pressed { background-color: #888888; }
        """)

        # 3. Текст
        label = QLabel(f"Этаж {floor_num}")
        label.setStyleSheet("color: #111; font-weight: bold; font-family: Arial; font-size: 13px;")

        layout.addWidget(self.lamp, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

    def set_led(self, state):
        if state:
            # Ярко-зеленый (включена)
            self.lamp.setStyleSheet("background-color: #00FF00; border-radius: 6px; border: 1px solid #00FF00;")
        else:
            self.lamp.setStyleSheet("background-color: #004400; border-radius: 6px; border: 1px solid #333;")

class CabinPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(130)
        # Светло-серый фон как на твоем фото
        self.setStyleSheet("background-color: #E0E0E0; border: 2px solid #BCBCBC; border-radius: 5px;")

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 20, 10, 20)
        main_layout.setSpacing(30)  # Расстояние между этажами

        self.floor_units = {}

        for i in [3, 2, 1]:
            unit = ElevatorControlBlock(i)
            self.floor_units[i] = unit
            main_layout.addWidget(unit)

        self.setLayout(main_layout)


class FloorPanel(QGraphicsItemGroup):
    def __init__(self, floor_num, parent=None):
        super().__init__(parent)
        self.floor_num = floor_num

        self.bg = QGraphicsRectItem(-15, -20, 80, 120)
        self.bg.setBrush(QBrush(QColor("#CCCCCB")))  # Тот самый сине-серый цвет
        self.bg.setPen(QPen(Qt.GlobalColor.black, 3))  # Жирная черная рамка
        self.addToGroup(self.bg)

        # 1. ЛАМПОЧКА (Зеленый "батончик" сверху)
        # Делаем ее вытянутой (35x12), как в коде кабины
        self.lamp = QGraphicsRectItem(10, 0, 30, 12)
        self.lamp.setBrush(QBrush(QColor("#004400")))  # Темно-зеленый (выкл)
        self.lamp.setPen(QPen(QColor("#222222"), 1))
        # Скругляем углы (в QGraphicsRectItem это делается через метод или отрисовку,
        # но для простоты на малинке оставим прямыми или используем Ellipse)
        self.addToGroup(self.lamp)

        # 2. КНОПКА (Большой серый квадрат 55x55)
        self.button = QGraphicsRectItem(0, 20, 50, 50)
        self.button.setBrush(QBrush(QColor("#666666")))  # Цвет как в кабине
        self.button.setPen(QPen(QColor("#444444"), 3))  # Жирная рамка 3px
        self.addToGroup(self.button)




    def set_lamp_state(self, active):
        color = QColor("#00FF00") if active else QColor("#004400")
        self.lamp.setBrush(QBrush(color))
        # Если активно, можно добавить "свечение" (убрать рамку)
        if active:
            self.lamp.setPen(QPen(QColor("#00FF00"), 1))
        else:
            self.lamp.setPen(QPen(QColor("#222222"), 1))
