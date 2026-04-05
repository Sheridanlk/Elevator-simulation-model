from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsItemGroup, \
    QFrame, QVBoxLayout, QLabel, QPushButton, QWidget, QGraphicsTextItem
from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QTimer, QRectF
from PyQt6.QtGui import QPainter, QPen, QFont
from PyQt6.QtGui import QColor, QBrush



class ElevatorCabin(QGraphicsItemGroup):
    def __init__(self):
        super().__init__()

        # Кабина
        self.body = QGraphicsRectItem(0, 0, 220, 230)
        #self.body = QGraphicsSvgItem("Assets/cabin.svg")
        self.body.setBrush(QBrush(QColor("#34495e")))
        self.addToGroup(self.body)

        # Левая и правая створки
        self.door_l = QGraphicsRectItem(35, 20, 75, 190)
        #self.door_l = QGraphicsSvgItem("Assets/door_left.svg")
        self.door_l.setBrush(QBrush(QColor("#bdc3c7")))
        self.addToGroup(self.door_l)

        self.door_r = QGraphicsRectItem(110, 20, 75, 190)
        #self.door_r = QGraphicsSvgItem("Assets/door_right.svg")
        self.door_r.setBrush(QBrush(QColor("#bdc3c7")))
        self.addToGroup(self.door_r)

        # Датчики дверей ВКО/ВКЗ
        self.led_vko = QGraphicsEllipseItem(15, -15, 10, 10)
        self.led_vkz = QGraphicsEllipseItem(55, -15, 10, 10)
        for led in [self.led_vko, self.led_vkz]:
            led.setBrush(QBrush(Qt.GlobalColor.black))
            self.addToGroup(led)

    def set_door_position(self, value):
        offset = value * 75  # Ширина сдвига
        self.door_l.setPos(-offset, 0)
        self.door_r.setPos(offset, 0)

    def set_door_leds(self, vko, vkz):
        self.led_vko.setBrush(QBrush(Qt.GlobalColor.cyan if vko else Qt.GlobalColor.black))
        self.led_vkz.setBrush(QBrush(Qt.GlobalColor.red if vkz else Qt.GlobalColor.black))


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

        self.cabin = ElevatorCabin()
        self.scene.addItem(self.cabin)

    def _init_shaft(self):

        self.shaft_svg = QGraphicsSvgItem("Assets/vent.svg")
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
                grp, bg = self.create_sensor_label(f"{f}{names[s_type]}", x_pos, y_pos, LABEL_WIDTH, LABEL_HEIGHT)
                self.floor_leds[f"f{f}_{s_type}"] = bg

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
            led.setBrush(QBrush(QColor(173, 255, 47) if active else QColor(107, 121, 16)))

    def resizeEvent(self, event):
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def create_sensor_label(self, text_str, x, y, width=40, height=25):
        # 1. Задаем цвета из твоего референса
        olive_color = QColor(107, 121, 16)  # Примерный оливковый
        black_color = QColor(0, 0, 0)
        # Цвет для "зажженного" состояния (например, ярко-салатовый)
        active_color = QColor(173, 255, 47)

        # 2. Создаем фон (скругленный прямоугольник)
        bg_rect = QGraphicsRectItem(0, 0, width, height)
        # Настраиваем рамку ( Pen) - черная, толстая
        bg_rect.setPen(QPen(black_color, 2))
        # Настраиваем заливку (Brush) - оливковая
        bg_rect.setBrush(QBrush(olive_color))

        # 3. Делаем углы скругленными (магия Qt)
        # Внутренний радиус скругления, попробуй 5 или 7 пикселей
        bg_rect.setRect(0, 0, width, height)
        bg_rect.setPos(x, y)  # Сначала ставим позицию группы, чтобы rect был в local (0,0)

        # *Важно*: Чтобы setRect работал со скруглением, используй drawRoundedRect в painter,
        # или, что проще для Items, используй QGraphicsPathItem.
        # Давай сделаем через Path для идеального скругления:
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, width, height), 5, 5)  # Радиус скругления 7

        from PyQt6.QtWidgets import QGraphicsPathItem
        bg_item = QGraphicsPathItem(path)
        bg_item.setPen(QPen(black_color, 2))
        bg_item.setBrush(QBrush(olive_color))
        bg_item.setPos(x, y)

        # 4. Создаем текст
        text_item = QGraphicsTextItem(text_str)
        # Шриф Arial, полужирный, размер подбираем (например, 10 или 12)
        font = QFont("Arial", 11, QFont.Weight.Bold)
        text_item.setFont(font)
        text_item.setDefaultTextColor(black_color)

        # 5. Центрируем текст внутри прямоугольника
        text_rect = text_item.boundingRect()
        # Вычисляем смещение, чтобы центр текста совпал с центром прямоугольника
        off_x = (width - text_rect.width()) / 2
        off_y = (height - text_rect.height()) / 2
        text_item.setPos(x + off_x, y + off_y)

        # 6. Группируем их, чтобы двигать как одно целое
        label_group = QGraphicsItemGroup()
        self.scene.addItem(label_group)  # Сначала добавляем группу в сцену

        label_group.addToGroup(bg_item)
        label_group.addToGroup(text_item)
        label_group.setZValue(10)  # Выше шахты и кабины

        # Сохраняем ссылку на фон, чтобы потом менять его цвет!
        return label_group, bg_item





class Toast(QFrame):
    def __init__(self, parent, text, is_error=True):
        super().__init__(parent)
        self.setFixedSize(280, 45)

        # Цвета: красный для алармов, темно-серый для инфо
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
        x = parent.width() - self.width() - margin
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
