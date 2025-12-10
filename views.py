from typing import Tuple
import time
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QGraphicsScene,
    QGraphicsView,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
    QMessageBox,
    QGraphicsRectItem,
    QLabel,
    QGraphicsOpacityEffect,
    QGroupBox,
)
from PyQt5.QtCore import QTimer, Qt, QEasingCurve, QPoint
from PyQt5.QtGui import QColor, QPainter, QFont, QPalette, QIcon, QBrush

from config import CONFIG
from models import LiftModel, DoorModel


# Expose lamp radius as a module-level constant for convenience
LAMP_RADIUS: float = CONFIG["lamp_radius"]


class SensorLamp:
    """A small circular indicator light drawn on the scene."""

    def __init__(self, scene: QGraphicsScene, x: float, y: float) -> None:
        # Create an ellipse item centered at (x, y)
        self.item = scene.addEllipse(
            x - LAMP_RADIUS,
            y - LAMP_RADIUS,
            LAMP_RADIUS * 2,
            LAMP_RADIUS * 2,
            brush=QBrush(QColor("gray")),
        )

    def set_active(self, active: bool) -> None:
        """Set the lamp colour based on its active state."""
        self.item.setBrush(QBrush(QColor("red") if active else QColor("gray")))

    def set_pos(self, x: float, y: float) -> None:
        """Reposition the lamp to a new centre coordinate."""
        self.item.setRect(
            x - LAMP_RADIUS,
            y - LAMP_RADIUS,
            LAMP_RADIUS * 2,
            LAMP_RADIUS * 2,
        )


class LiftView(QMainWindow):
    """Main window that renders the lift and handles user interactions."""

    def __init__(self, lift_model: LiftModel, door_model: DoorModel, config: dict, gpio_handler=None) -> None:
        super().__init__()

        # Store references
        self.lift_model = lift_model
        self.door_model = door_model
        self.config = config
        # Optional GPIO handler for driving real hardware
        self.gpio_handler = gpio_handler

        # Cache frequently used configuration values
        self.field_width = config["field_width"]
        self.field_height = config["field_height"]
        self.lift_width = config["lift_width"]
        self.lift_height = config["lift_height"]

        self.setWindowTitle("Лифт")

        # Cooldown for displaying repeated alarms
        self._alarm_last: dict = {}
        self._alarm_cooldown = 1.5

        self._toast: QLabel | None = None
        self._toast_timer: QTimer | None = None
        self._toast_anim = None

        # Layout setup
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Graphics scene and view
        self.scene = QGraphicsScene(0, 0, self.field_width, self.field_height)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setAlignment(Qt.AlignCenter | Qt.AlignCenter)
        layout.addWidget(self.view)

        # UI panel on the right
        ui_layout = QVBoxLayout()
        ui_layout.setContentsMargins(6, 6, 6, 6)
        ui_layout.setSpacing(8)
        layout.addLayout(ui_layout)

        # ------------------------------------------------------------------
        # Grouped controls on the right-hand panel
        # ------------------------------------------------------------------
        # 1) Cabin floor selection (buttons inside the cabin)
        cab_group = QGroupBox("Выбор этажа (кабина)")
        cab_layout = QVBoxLayout()
        cab_layout.setSpacing(4)
        cab_group.setLayout(cab_layout)
        from functools import partial
        self.cabin_buttons = []
        for floor in range(self.lift_model.num_floors):
            btn = QPushButton(f"Этаж {floor + 1}")
            btn.setCheckable(False)  # больше НЕ чекбокс
            # серый фон по умолчанию — лампа
            btn.setStyleSheet("background-color: #CCCCCC;")
            # при Нажатии отправляем импульс на выход
            btn.pressed.connect(partial(self.on_cabin_button_pressed, floor))
            cab_layout.addWidget(btn)
            self.cabin_buttons.append(btn)

        ui_layout.addWidget(cab_group)

        # 2) Cabin movement controls (up/down and slow mode)
        move_group = QGroupBox("Управление кабиной")
        move_layout = QVBoxLayout()
        move_layout.setSpacing(6)
        move_group.setLayout(move_layout)
        self.up_btn = QPushButton("Вверх")
        self.down_btn = QPushButton("Вниз")
        move_layout.addWidget(self.up_btn)
        move_layout.addWidget(self.down_btn)
        self.slow_chk = QCheckBox("Пониженная скорость")
        move_layout.addWidget(self.slow_chk)
        # GUI-флаг (что хочет пользователь в интерфейсе)
        self.gui_slow_enabled = False
        # GPIO-флаг (что пришло с входа slow_mode)
        self.gpio_slow_enabled = False
        self.lift_model.toggle_slow(False)
        # Connect signals
        self.up_btn.pressed.connect(self.start_up)
        self.up_btn.released.connect(self.stop_move)
        self.down_btn.pressed.connect(self.start_down)
        self.down_btn.released.connect(self.stop_move)
        self.slow_chk.stateChanged.connect(self.toggle_slow)
        ui_layout.addWidget(move_group)

        # 3) Door controls (open/close)
        door_group = QGroupBox("Управление дверью")
        door_layout = QVBoxLayout()
        door_layout.setSpacing(6)
        door_group.setLayout(door_layout)
        self.open_btn = QPushButton("Открыть дверь")
        self.close_btn = QPushButton("Закрыть дверь")
        door_layout.addWidget(self.open_btn)
        door_layout.addWidget(self.close_btn)
        # Connect signals
        self.open_btn.pressed.connect(self.start_open)
        self.open_btn.released.connect(self.stop_door)
        self.close_btn.pressed.connect(self.start_close)
        self.close_btn.released.connect(self.stop_door)
        ui_layout.addWidget(door_group)

        # Draw floors
        self.floor_rects = []
        for floor in range(self.lift_model.num_floors):
            # Draw floor rectangles from bottom to top using sensor positions
            base_y = self.lift_model.sensors[floor][0]
            rect = self.scene.addRect(
                20,
                base_y,
                self.field_width - 40,
                self.lift_model.floor_height,
                brush=QBrush(QColor("lightgray")),
            )
            self.floor_rects.append(rect)

        # Floor call buttons (one button per floor).  These are drawn on
        # the scene near each floor.  They do not trigger any action in
        # the simulation but update the GPIO outputs when clicked.
        self.floor_button_states = [False] * self.lift_model.num_floors
        self.floor_buttons_items = []
        button_w = 30 * (self.config.get("k", 1))
        button_h = 20 * (self.config.get("k", 1))
        call_x = 5  # X position from the left edge
        for floor in range(self.lift_model.num_floors):
            # Position call buttons based on sensor positions
            base_y = self.lift_model.sensors[floor][0]
            y = base_y + (self.lift_model.floor_height - button_h) / 2
            # Create a rectangle item and store its floor index via a custom property
            item = self.scene.addRect(
                call_x,
                y,
                button_w,
                button_h,
                brush=QBrush(QColor("#CCCCCC")),
            )
            # Add a simple text label for the floor number
            label = self.scene.addText(str(floor + 1))
            label.setDefaultTextColor(QColor("black"))
            # Center the text within the rectangle
            label_x = call_x + (button_w - label.boundingRect().width()) / 2
            label_y = y + (button_h - label.boundingRect().height()) / 2
            label.setPos(label_x, label_y)
            # Enable mouse events on the button
            item.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
            item.setData(0, floor)  # Store floor index in custom role
            self.floor_buttons_items.append(item)
        # Capture mouse press events on the scene for floor buttons
        self.scene.mousePressEvent = self._scene_mousePressEvent

        # Cabin rectangle
        self.cabin_x = (self.field_width - self.lift_width) / 2
        self.cabin_y = self.lift_model.position - self.lift_height / 2
        self.cabin_item = self.scene.addRect(
            self.cabin_x,
            self.cabin_y,
            self.lift_width,
            self.lift_height,
            brush=QBrush(QColor("#2E68FF")),
        )

        # Door rectangle (moved by setting its position)
        self.door_item = QGraphicsRectItem(0, 0, self.lift_width, self.lift_height)
        self.door_item.setBrush(QBrush(QColor("#5C7AEA")))
        self.scene.addItem(self.door_item)
        door_left = self.door_model.get_leaf_left_px(self.cabin_x)
        self.door_item.setPos(door_left, self.cabin_y)

        # Floor sensor lamps (three per floor) positioned at the right edge
        self.floor_lamps: list[list[SensorLamp]] = []
        lamp_x = self.field_width - LAMP_RADIUS - 2
        for floor in range(self.lift_model.num_floors):
            # Place lamps based on sensor positions
            top_y = self.lift_model.sensors[floor][0]
            centre_y = self.lift_model.sensors[floor][1]
            bottom_y = self.lift_model.sensors[floor][2]
            self.floor_lamps.append(
                [
                    SensorLamp(self.scene, lamp_x, top_y),
                    SensorLamp(self.scene, lamp_x, centre_y),
                    SensorLamp(self.scene, lamp_x, bottom_y),
                ]
            )

        # Door indicator lamps (above the cabin, ride along with the cabin)
        lamp_y = self.cabin_y - 14
        self.door_closed_lamp = SensorLamp(
            self.scene, self.cabin_x + self.lift_width * 0.35, lamp_y
        )
        self.door_open_lamp = SensorLamp(
            self.scene, self.cabin_x + self.lift_width * 0.65, lamp_y
        )

        # Timer for animation and movement
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)

        # Флаги движения:
        # от GUI (кнопки интерфейса)
        self.gui_moving_up = False
        self.gui_moving_down = False
        # от GPIO (физические кнопки/ПЛК)
        self.gpio_moving_up = False
        self.gpio_moving_down = False
        # итоговые флаги, которые использует tick()
        self.moving_up = False
        self.moving_down = False

        # Флаги двери: отдельно от GUI и от GPIO
        self.gui_opening = False
        self.gui_closing = False
        self.gpio_opening = False
        self.gpio_closing = False
        # итоговые флаги двери, которые использует tick()
        self.opening = False
        self.closing = False

        #timer for inputs
        self.gpio_poll_timer = None
        if self.gpio_handler is not None:
            self.gpio_poll_timer = QTimer(self)
            self.gpio_poll_timer.timeout.connect(self.poll_gpio_inputs)
            self.gpio_poll_timer.start(50)  # опрос каждые 50 мс

        # Initial update and display
        self.update_all()
        self.showMaximized()

    def set_button_color(self, button: QPushButton, color: str):
        pal = button.palette()
        pal.setColor(QPalette.Button, QColor(color))
        button.setAutoFillBackground(True)
        button.setPalette(pal)
        button.update()
    def _update_motion_flags(self) -> None:
        """Пересчитать итоговые флаги движения из источников GUI и GPIO."""
        prev_up = self.moving_up
        prev_down = self.moving_down

        self.moving_up = self.gui_moving_up or self.gpio_moving_up
        self.moving_down = self.gui_moving_down or self.gpio_moving_down

        # Если раньше никто не двигался, а теперь есть движение — запускаем таймер
        if (self.moving_up or self.moving_down) and not self.timer.isActive():
            self.timer.start(20)

    def _update_door_flags(self) -> None:
        """Пересчитать итоговые флаги двери из источников GUI и GPIO."""
        self.opening = self.gui_opening or self.gpio_opening
        self.closing = self.gui_closing or self.gpio_closing

        # Если дверь начала двигаться — убедимся, что таймер запущен
        if (self.opening or self.closing) and not self.timer.isActive():
            self.timer.start(20)
    # --------------------------------------------------------------
    # Movement and door control event handlers
    # --------------------------------------------------------------
    def start_up(self) -> None:
        left_ok, _ = self.door_model.get_edge_sensors_active()
        if not left_ok:
            self.alarm_once("move_with_open_door", "Авария: движение с открытой дверью.")
        self.gui_moving_up = True
        self.gui_moving_down = False
        self._update_motion_flags()

    def start_down(self) -> None:
        left_ok, _ = self.door_model.get_edge_sensors_active()
        if not left_ok:
            self.alarm_once("move_with_open_door", "Авария: движение с открытой дверью.")
        self.gui_moving_down = True
        self.gui_moving_up = False
        self._update_motion_flags()

    def stop_move(self) -> None:
        self.gui_moving_up = False
        self.gui_moving_down = False
        self._update_motion_flags()

    def toggle_slow(self, state) -> None:
        """Обработчик изменения чекбокса 'Пониженная скорость' из GUI."""
        want_slow = (state == Qt.Checked)

        # Если GPIO ВЫНУЖДАЕТ медленный ход — не даём GUI его выключать
        if self.gpio_slow_enabled:
            # Возвращаем чекбокс обратно в "галочку", если его пытались снять
            self.slow_chk.blockSignals(True)
            self.slow_chk.setChecked(True)
            self.slow_chk.blockSignals(False)
            # Модель уже должна быть в slow-режиме, просто выходим
            return

        # Здесь управляющим источником является GUI
        self.gui_slow_enabled = want_slow
        self.lift_model.toggle_slow(self.gui_slow_enabled)

    def start_open(self) -> None:
        # Эта функция вызывается ТОЛЬКО из GUI (кнопки на панели)
        if self.moving_up or self.moving_down:
            self.alarm_once(
                "open_while_moving", "Авария: попытка открыть дверь во время движения."
            )
        if not self.lift_model.is_on_floor_center():
            self.alarm_once("open_off_floor", "Авария: попытка открыть дверь вне этажа.")

        self.gui_opening = True
        self.gui_closing = False
        self._update_door_flags()

    def start_close(self) -> None:
        # Тоже только GUI
        self.gui_closing = True
        self.gui_opening = False
        self._update_door_flags()

    def stop_door(self) -> None:
        # Отпустили GUI-кнопку — GUI больше не просит двигать дверь
        self.gui_opening = False
        self.gui_closing = False
        self._update_door_flags()

    # --------------------------------------------------------------
    # Alarm and toast notifications
    # --------------------------------------------------------------
    def alarm_once(self, key: str, text: str) -> None:
        now = time.monotonic()
        last = self._alarm_last.get(key, 0.0)
        if now - last >= self._alarm_cooldown:
            self._alarm_last[key] = now
            self.show_toast(text)

    def show_toast(self, text: str, msec: int = 2000) -> None:
        parent = self.centralWidget()
        if self._toast is None:
            lbl = QLabel("", parent)
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lbl.setMargin(10)
            lbl.setWordWrap(True)
            # Dark translucent background with rounded corners
            lbl.setStyleSheet(
                """
                QLabel {
                    background: rgba(255, 0, 0, 1);
                    color: white;
                    border-radius: 10px;
                    font-size: 12pt;
                }
            """
            )
            eff = QGraphicsOpacityEffect(lbl)
            lbl.setGraphicsEffect(eff)
            self._toast = lbl
            self._toast_timer = QTimer(self)
            self._toast_timer.setSingleShot(True)
            self._toast_timer.timeout.connect(self._fade_out)
            from PyQt5.QtCore import QPropertyAnimation

            self._toast_anim = QPropertyAnimation(eff, b"opacity", self)
            self._toast_anim.setEasingCurve(QEasingCurve.InOutQuad)
        else:
            lbl = self._toast
        # Update text and limit width
        lbl.setText(text)
        lbl.adjustSize()
        maxw = int(self.width() * 0.5)
        if lbl.width() > maxw:
            lbl.setFixedWidth(maxw)
            lbl.adjustSize()
        # Position in bottom-right corner
        margin = 14
        x = self.width() - lbl.width() - margin
        y = self.height() - lbl.height() - margin
        lbl.move(x, y)
        # Show immediately and start timer to fade out
        eff = lbl.graphicsEffect()
        eff.setOpacity(1.0)
        lbl.show()
        lbl.raise_()
        self._toast_timer.start(msec)

    def _fade_out(self, msec: int = 350) -> None:
        anim = self._toast_anim
        eff = self._toast.graphicsEffect()
        anim.stop()
        anim.setDuration(msec)
        anim.setStartValue(eff.opacity())
        anim.setEndValue(0.0)
        anim.finished.connect(self._toast.hide)
        anim.start()

    # --------------------------------------------------------------
    # Main animation tick
    # --------------------------------------------------------------

    def poll_gpio_inputs(self) -> None:
        """Опрос дискретных входов Raspberry Pi и управление лифтом через них."""
        if self.gpio_handler is None:
            return

        inputs = self.gpio_handler.read_inputs()

        # Имена ключей — как в gpio_handler.input_pins
        move_up = bool(inputs.get("up", False))
        move_down = bool(inputs.get("down", False))
        slow = bool(inputs.get("slow_mode", False))
        door_open = bool(inputs.get("open_door", False))
        door_close = bool(inputs.get("close_door", False))

        # ---------- ДВИЖЕНИЕ от GPIO ----------
        if move_up or move_down:
            if move_up and move_down:
                # конфликт — никуда не едем
                self.gpio_moving_up = False
                self.gpio_moving_down = False
            else:
                self.gpio_moving_up = move_up
                self.gpio_moving_down = move_down
        else:
            # Кнопки на входах отпущены — GPIO больше не задаёт движение
            self.gpio_moving_up = False
            self.gpio_moving_down = False

        # Пересчитываем итоговое движение с учётом GUI-флагов
        self._update_motion_flags()

        # ---------- ДВЕРЬ от GPIO ----------
        if door_open or door_close:
            if door_open and not door_close:
                # Команда "открыть" от ПЛК
                if self.moving_up or self.moving_down:
                    self.alarm_once(
                        "open_while_moving",
                        "Авария: попытка открыть дверь во время движения.",
                    )
                if not self.lift_model.is_on_floor_center():
                    self.alarm_once(
                        "open_off_floor",
                        "Авария: попытка открыть дверь вне этажа.",
                    )
                self.gpio_opening = True
                self.gpio_closing = False
            elif door_close and not door_open:
                # Команда "закрыть" от ПЛК
                self.gpio_closing = True
                self.gpio_opening = False
            else:
                # Оба входа активны или непонятное состояние — стоп двери
                self.gpio_opening = False
                self.gpio_closing = False
        else:
            # Входы отпущены — ПЛК больше не управляет дверью
            self.gpio_opening = False
            self.gpio_closing = False

        # Пересчитать итоговые флаги opening/closing
        self._update_door_flags()

        # ---------- Пониженная скорость от GPIO ----------
        if slow:
            # Аппаратный вход активен — форсируем медленный ход
            if not self.gpio_slow_enabled:
                self.gpio_slow_enabled = True

                # Ставим чекбокс в "галочку" и блокируем его
                self.slow_chk.blockSignals(True)
                self.slow_chk.setChecked(True)
                self.slow_chk.setEnabled(False)
                self.slow_chk.blockSignals(False)

                # Включаем медленную скорость в модели
                self.lift_model.toggle_slow(True)
        else:
            # Вход slow_mode НЕ активен — аппаратного принуждения нет
            if self.gpio_slow_enabled:
                self.gpio_slow_enabled = False

                # Разблокируем чекбокс, его состояние снова управляет моделью
                self.slow_chk.blockSignals(True)
                self.slow_chk.setEnabled(True)
                self.slow_chk.setChecked(self.gui_slow_enabled)
                self.slow_chk.blockSignals(False)

                # Синхронизируем модель с тем, что хочет GUI
                self.lift_model.toggle_slow(self.gui_slow_enabled)
        # ---------- ЛАМПЫ КНОПОК от ПЛК ----------
        if self.gpio_handler is not None:
            try:
                cabin_lamps, floor_lamps = self.gpio_handler.read_button_lamps()
            except Exception:
                cabin_lamps, floor_lamps = [], []

            # лампы кнопок в кабине
            for idx, state in enumerate(cabin_lamps):
                if idx < len(self.cabin_buttons):
                    btn = self.cabin_buttons[idx]
                    # зелёный если лампа активна, серый если нет
                    self.set_button_color(btn, "#A6E3A1" if state else "#CCCCCC")

            # лампы кнопок на этажах
            for idx, state in enumerate(floor_lamps):
                if idx < len(self.floor_buttons_items):
                    item = self.floor_buttons_items[idx]
                    item.setBrush(QBrush(QColor("#A6E3A1" if state else "#CCCCCC")))

    def tick(self) -> None:
        try:
            # 1) Vertical movement
            if self.moving_up:
                self.lift_model.move_up()
            if self.moving_down:
                self.lift_model.move_down()
            # 2) Floor limit sensors
            top_lim = self.lift_model.top_limit()
            bot_lim = self.lift_model.bottom_limit()
            if self.moving_up and self.lift_model.position <= top_lim:
                self.update_geometry()
                self.update_lamps()
                self.alarm_once(
                    "going_beyond",
                    "Выход за верхний предел: сработал верхний аварийный датчик.",
                )
            if self.moving_down and self.lift_model.position >= bot_lim:
                self.update_geometry()
                self.update_lamps()
                self.alarm_once(
                    "going_beyond",
                    "Выход за нижний предел: сработал нижний аварийный датчик."
                )
            # 3) Door movement
            if self.opening and self.door_model.left_norm < 1.0:
                self.door_model.open_step()
            if self.closing and self.door_model.left_norm > 0.0:
                self.door_model.close_step()
            # 4) Redraw
            self.update_geometry()
            self.update_lamps()
            active_floor_matrix = self.lift_model.get_active_floor_sensors()
            # 5) Stop timer if nothing is moving
            if not (
                self.moving_up
                or self.moving_down
                or self.opening
                or self.closing
            ):
                self.timer.stop()
        except Exception as e:
            self.timer.stop()
            QMessageBox.critical(self, "Ошибка", f"{type(e).__name__}: {e}")

    # --------------------------------------------------------------
    # Scene update helpers
    # --------------------------------------------------------------
    def update_geometry(self) -> None:
        # Cabin position based on model state
        self.cabin_x = (self.field_width - self.lift_width) / 2
        self.cabin_y = self.lift_model.position - self.lift_height / 2
        self.cabin_item.setRect(
            self.cabin_x,
            self.cabin_y,
            self.lift_width,
            self.lift_height,
        )
        # Door leaf position
        door_left_px = self.door_model.get_leaf_left_px(self.cabin_x)
        self.door_item.setPos(door_left_px, self.cabin_y)
        # Door indicator lamps above cabin
        lamp_y = self.cabin_y - 14
        self.door_closed_lamp.set_pos(
            self.cabin_x + self.lift_width * 0.35, lamp_y
        )
        self.door_open_lamp.set_pos(
            self.cabin_x + self.lift_width * 0.65, lamp_y
        )

    def update_lamps(self) -> None:
        # Floor sensors
        active_floor = self.lift_model.get_active_floor_sensors()
        for floor_idx, row in enumerate(self.floor_lamps):
            for i, lamp in enumerate(row):
                lamp.set_active(active_floor[floor_idx][i])
        # Door edge sensors
        left_ok, right_ok = self.door_model.get_edge_sensors_active()
        self.door_closed_lamp.set_active(left_ok)
        self.door_open_lamp.set_active(right_ok)

        # Update GPIO outputs for floor sensors if a handler is provided
        if self.gpio_handler is not None:
            try:
                self.gpio_handler.update_floor_sensors(active_floor)
                self.gpio_handler.update_door_sensors(left_ok, right_ok)
            except Exception:
                # Ignore GPIO errors in GUI context
                pass


    def update_all(self) -> None:
        self.update_geometry()
        self.update_lamps()

    # --------------------------------------------------------------
    # Cabin button handling
    # --------------------------------------------------------------
    def on_cabin_button_pressed(self, idx: int) -> None:
        """Кнопка в кабине: послать короткий импульс на выход RPi."""
        if self.gpio_handler is None:
            return

        # краткий импульс HIGH -> LOW
        self.gpio_handler.set_cabin_button_output(idx, True)
        QTimer.singleShot(50, lambda: self.gpio_handler.set_cabin_button_output(idx, False))

    # --------------------------------------------------------------
    # Floor call button handling
    # --------------------------------------------------------------
    def _scene_mousePressEvent(self, event):
        pos = event.scenePos()
        # Check if the click was on one of the floor button items
        for item in self.floor_buttons_items:
            if item.contains(item.mapFromScene(pos)):
                # Retrieve floor index stored in the item's data role 0
                floor_idx = item.data(0)
                if floor_idx is not None:
                    self.on_floor_button_clicked(int(floor_idx))
                    # We handle the event; do not propagate further
                    return
        # Otherwise call the default QGraphicsScene implementation to allow other interactions
        QGraphicsScene.mousePressEvent(self.scene, event)

    def on_floor_button_clicked(self, idx: int) -> None:
        """Кнопка вызова на этаже: только импульс на выход, без latch."""
        if self.gpio_handler is None:
            return

        # краткий импульс HIGH -> LOW
        self.gpio_handler.set_floor_button_output(idx, True)
        QTimer.singleShot(50, lambda: self.gpio_handler.set_floor_button_output(idx, False))



__all__ = ["LiftView", "SensorLamp", "LAMP_RADIUS"]