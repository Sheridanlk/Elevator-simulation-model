"""
Graphical user interface for the lift simulation.

This module contains the PyQt-based ``LiftView`` class, which
visualises the state of a ``LiftModel`` and ``DoorModel``.  It also
includes a small ``SensorLamp`` helper for drawing indicator lights.

The view is parameterised by a configuration dictionary (see
``config.CONFIG``) that defines dimensions, speeds and other
properties.  The view itself does not modify the models directly;
instead, it invokes their methods in response to UI events.
"""

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
        self.cabin_button_states = [False] * self.lift_model.num_floors
        from functools import partial
        self.cabin_buttons = []
        for floor in range(self.lift_model.num_floors):
            btn = QPushButton(f"Этаж {floor + 1}")
            btn.setCheckable(True)
            btn.clicked.connect(partial(self.on_cabin_button_clicked, floor))
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
        self.moving_up = False
        self.moving_down = False
        self.opening = False
        self.closing = False

        # Initial update and display
        self.update_all()
        self.showMaximized()

    # --------------------------------------------------------------
    # Movement and door control event handlers
    # --------------------------------------------------------------
    def start_up(self) -> None:
        left_ok, _ = self.door_model.get_edge_sensors_active()
        if not left_ok:
            self.alarm_once("move_with_open_door", "Авария: движение с открытой дверью.")
        self.moving_up = True
        if not self.timer.isActive():
            self.timer.start(20)

    def start_down(self) -> None:
        left_ok, _ = self.door_model.get_edge_sensors_active()
        if not left_ok:
            self.alarm_once("move_with_open_door", "Авария: движение с открытой дверью.")
        self.moving_down = True
        if not self.timer.isActive():
            self.timer.start(20)

    def stop_move(self) -> None:
        self.moving_up = False
        self.moving_down = False

    def toggle_slow(self, state: int) -> None:
        self.lift_model.toggle_slow(state == Qt.Checked)

    def start_open(self) -> None:
        if self.moving_up or self.moving_down:
            self.alarm_once(
                "open_while_moving", "Авария: попытка открыть дверь во время движения."
            )
        if not self.lift_model.is_on_floor_center():
            self.alarm_once("open_off_floor", "Авария: попытка открыть дверь вне этажа.")
        self.opening = True
        self.closing = False
        if not self.timer.isActive():
            self.timer.start(20)

    def start_close(self) -> None:
        self.closing = True
        self.opening = False
        if not self.timer.isActive():
            self.timer.start(20)

    def stop_door(self) -> None:
        self.opening = False
        self.closing = False

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
        # Create or reuse a floating QLabel to display transient messages
        if self._toast is None:
            lbl = QLabel("", self)
            lbl.setWindowFlags(
                Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            )
            # Allow mouse clicks to pass through the label
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            lbl.setAttribute(Qt.WA_ShowWithoutActivating, True)
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lbl.setMargin(10)
            lbl.setWordWrap(True)
            # Dark translucent background with rounded corners
            lbl.setStyleSheet(
                """
                QLabel {
                    background: rgba(32,32,32,200);
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
            for idx, row in enumerate(active_floor_matrix):
                if row[1]:
                    _, door_open_ok = self.door_model.get_edge_sensors_active()
                    if door_open_ok:
                        if self.floor_button_states[idx]:
                            self.floor_button_states[idx] = False
                            self.floor_buttons_items[idx].setBrush(QBrush(QColor("#CCCCCC")))
                        # Сбросить кнопку в кабине, если она была нажата
                        if self.cabin_button_states[idx]:
                            self.cabin_button_states[idx] = False
                            self.cabin_buttons[idx].setChecked(False)
                        # Обновить состояния GPIO, если используется gpio_handler
                        if self.gpio_handler:
                            self.gpio_handler.update_floor_buttons(self.floor_button_states)
                            self.gpio_handler.update_cabin_buttons(self.cabin_button_states)
                    break  # выходим из цикла, т.к. кабина может быть на одном этаже одновременно
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
            except Exception:
                # Ignore GPIO errors in GUI context
                pass

    def update_all(self) -> None:
        self.update_geometry()
        self.update_lamps()

    # --------------------------------------------------------------
    # Cabin button handling
    # --------------------------------------------------------------
    def on_cabin_button_clicked(self, idx: int) -> None:
        """Handle clicks on the cabin floor buttons.

        When a cabin button is clicked, its state is toggled and the
        corresponding GPIO output is updated (if a handler is available).
        """
        # Toggle the internal state
        self.cabin_button_states[idx] = not self.cabin_button_states[idx]
        # Update the button's checked appearance
        btn = self.cabin_buttons[idx]
        btn.setChecked(self.cabin_button_states[idx])
        # Update GPIO outputs if handler available
        if self.gpio_handler is not None:
            try:
                self.gpio_handler.update_cabin_buttons(self.cabin_button_states)
            except Exception:
                pass

    # --------------------------------------------------------------
    # Floor call button handling
    # --------------------------------------------------------------
    def _scene_mousePressEvent(self, event):
        """Intercept mouse presses on the scene to handle floor call buttons."""
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
        """Handle clicks on the external floor call buttons."""
        # Toggle state
        self.floor_button_states[idx] = not self.floor_button_states[idx]
        # Update button colour to reflect state
        item = self.floor_buttons_items[idx]
        if self.floor_button_states[idx]:
            item.setBrush(QBrush(QColor("#A6E3A1")))  # Greenish when pressed
        else:
            item.setBrush(QBrush(QColor("#CCCCCC")))
        # Update GPIO outputs
        if self.gpio_handler is not None:
            try:
                self.gpio_handler.update_floor_buttons(self.floor_button_states)
            except Exception:
                pass


__all__ = ["LiftView", "SensorLamp", "LAMP_RADIUS"]