from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsItemGroup, \
    QFrame, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtGui import QColor, QBrush

class ElevatorCabin(QGraphicsItemGroup):
    def __init__(self):
        super().__init__()

        # Кабина
        self.body = QGraphicsRectItem(0, 0, 80, 100)
        #self.body = QGraphicsSvgItem("Assets/cabin.svg")
        self.body.setBrush(QBrush(QColor("#34495e")))
        self.addToGroup(self.body)

        # Левая и правая створки
        self.door_l = QGraphicsRectItem(0, 0, 40, 100)
        #self.door_l = QGraphicsSvgItem("Assets/door_left.svg")
        self.door_l.setBrush(QBrush(QColor("#bdc3c7")))
        self.addToGroup(self.door_l)

        self.door_r = QGraphicsRectItem(40, 0, 40, 100)
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
        offset = value * 35  # Ширина сдвига
        self.door_l.setPos(-offset, 0)
        self.door_r.setPos(offset, 0)

    def set_door_leds(self, vko, vkz):
        self.led_vko.setBrush(QBrush(Qt.GlobalColor.cyan if vko else Qt.GlobalColor.black))
        self.led_vkz.setBrush(QBrush(Qt.GlobalColor.red if vkz else Qt.GlobalColor.black))


class ElevatorView(QGraphicsView):
    def __init__(self, model):
        super().__init__()
        self.model = model
        self.scene = QGraphicsScene(0, 0, 400, 1000)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Параметры отрисовки
        self.cabin_height_px = 100
        self.scale_m = 70
        self.ground_y = 850

        # Создаем объекты
        self._init_shaft()
        self._init_floor_sensors()

        self.cabin = ElevatorCabin()
        self.scene.addItem(self.cabin)

    def _init_shaft(self):
        total_m = self.model.MAX_POS - self.model.MIN_POS
        shaft_height_px = total_m * self.scale_m

        top_y = self.ground_y - (self.model.MAX_POS * self.scale_m)  # 50px запас отрисовки

        shaft = QGraphicsRectItem(100, top_y, 100, shaft_height_px + 100)
        shaft.setBrush(QBrush(QColor("#1a1a1a")))
        shaft.setPen(QPen(QColor("#444"), 2))
        shaft.setZValue(-1)
        self.scene.addItem(shaft)

    def _init_floor_sensors(self):
        self.floor_leds = {}
        for f, h in self.model.FLOORS.items():
            for s_type, offset in [("up", 0.5), ("mid", 0), ("down", -0.5)]:
                led = QGraphicsEllipseItem(0, 0, 12, 12)
                led.setBrush(QBrush(Qt.GlobalColor.darkRed))

                # Расчет Y (инвертируем, так как в Qt Y растет вниз)
                y_pos = self.ground_y - (h + offset) * self.scale_m - 6
                led.setPos(75, y_pos)

                self.scene.addItem(led)
                self.floor_leds[f"f{f}_{s_type}"] = led

    def update_ui(self, sensors):
        # Позиция кабины
        center_y_px = self.ground_y - (self.model.position * self.scale_m)
        draw_y = center_y_px - (self.cabin_height_px / 2)
        self.cabin.setPos(110, draw_y)

        # Состояние дверей
        self.cabin.set_door_position(self.model.door_pos)
        self.cabin.set_door_leds(sensors["vko"], sensors["vkz"])

        # Состояние этажных датчиков
        for key, led in self.floor_leds.items():
            active = sensors.get(key, False)
            led.setBrush(QBrush(Qt.GlobalColor.green if active else Qt.GlobalColor.darkRed))

    def resizeEvent(self, event):
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


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
