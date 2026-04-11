# main.py
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QCheckBox, \
    QGroupBox, QRadioButton, QFrame, QLabel
from PyQt6.QtCore import QTimer, Qt
from elevator_model import ElevatorModel
from elevator_ui import ElevatorView, Toast
from gpio_handler import GPIOHandler


class ElevatorSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.gpio = GPIOHandler()
        self.setWindowTitle("Лифт")
        #self.setStyleSheet("background-color: #1e1e1e; color: #ecf0f1;")
        self.active_alarms = {}

        self.model = ElevatorModel()
        self.view = ElevatorView(self.model)

        # Сборка интерфейса
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)


        self.cabin_panel = CabinPanel()
        layout.addWidget(self.cabin_panel, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # Лево: Графика
        layout.addWidget(self.view, stretch=3)

        control_panel = QFrame()
        control_panel.setStyleSheet("""
                    QFrame { 
                        background-color: #2d2d2d; 
                        border-left: 2px solid #3d3d3d; 
                        border-radius: 0px; 
                    }
                    QGroupBox {
                        color: #ecf0f1;
                        font-weight: bold;
                        border: 1px solid #3d3d3d;
                        margin-top: 10px;
                        padding-top: 15px;
                    }
                    QRadioButton {
                        color: #bdc3c7;
                    }
                    QLabel {
                        color: #ecf0f1;
                    }
                """)
        panel_layout = QVBoxLayout()
        control_panel.setLayout(panel_layout)
        layout.addWidget(control_panel, stretch=0)

        # Управление
        control_group = QGroupBox("Управление")
        control_layout = QVBoxLayout()
        self.radio_manual = QRadioButton("Ручное")
        self.radio_controller = QRadioButton("От контройлера")
        self.radio_manual.setChecked(True)

        for r in [self.radio_manual, self.radio_controller]:
            control_layout.addWidget(r)
        control_group.setLayout(control_layout)

        # Кабина
        self.lift_group = QGroupBox("Кабина")
        lift_layout = QVBoxLayout()
        self.radio_up = QRadioButton("Вверх")
        self.radio_stop = QRadioButton("Стоп")
        self.radio_down = QRadioButton("Вниз")
        self.radio_stop.setChecked(True)

        for r in [self.radio_up, self.radio_stop, self.radio_down]:
            lift_layout.addWidget(r)
        self.lift_group.setLayout(lift_layout)

        # Двери
        self.door_group = QGroupBox("Двери")
        door_layout = QVBoxLayout()
        self.radio_open = QRadioButton("Открыть")
        self.radio_d_stop = QRadioButton("Стоп")
        self.radio_close = QRadioButton("Закрыть")
        self.radio_d_stop.setChecked(True)

        for r in [self.radio_open, self.radio_d_stop, self.radio_close]:
            door_layout.addWidget(r)
        self.door_group.setLayout(door_layout)

        # Скорость кабины
        self.speed_group = QGroupBox("Скорость кабины")
        speed_layout = QVBoxLayout()
        self.radio_fast = QRadioButton("Нормальная")
        self.radio_slow = QRadioButton("Пониженная")
        self.radio_fast.setChecked(True)

        for r in [self.radio_fast, self.radio_slow]:
            speed_layout.addWidget(r)
        self.speed_group.setLayout(speed_layout)

        panel_layout.addWidget(control_group)
        panel_layout.addWidget(self.lift_group)
        panel_layout.addWidget(self.speed_group)
        panel_layout.addWidget(self.door_group)

        self.btn_reset = QPushButton("СБРОС ПОЛОЖЕНИЯ")
        self.btn_reset.setStyleSheet("""
            QPushButton { 
                background-color: #2980b9; 
                color: white; 
                font-weight: bold; 
                padding: 10px; 
                border-radius: 5px; 
            }
            QPushButton:pressed { background-color: #3498db; }
        """)
        self.btn_reset.clicked.connect(self.reset_simulator)
        panel_layout.addWidget(self.btn_reset)

        # Запуск цикла (50 раз в секунду)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_simulation)
        self.timer.start(20)

    def update_simulation(self):
        dt = 0.02  # 20 миллисекунд
        self.lift_group.setEnabled(True)
        self.door_group.setEnabled(True)
        self.speed_group.setEnabled(True)
        plc_inputs = {}

        # ОБРАБОТКА ТАЙМЕРОВ КНОПОК
        self.cabin_panel.update_timers(dt)

        # Читаем состояние кнопок
        if self.radio_manual.isChecked():
            cmds = {
                'up': self.radio_up.isChecked(),
                'down': self.radio_down.isChecked(),
                'low_speed': self.radio_slow.isChecked(),
                'open': self.radio_open.isChecked(),
                'close': self.radio_close.isChecked()
            }
        else:
            self.lift_group.setEnabled(False)
            self.door_group.setEnabled(False)
            self.speed_group.setEnabled(False)
            plc_inputs = self.gpio.read_inputs()
            cmds = plc_inputs

            for floor in [1, 2, 3]:
                lamp_key = f'l_c{floor}'
                if lamp_key in plc_inputs:
                    self.cabin_panel.floor_units[floor].set_led(plc_inputs[lamp_key])



        # Считаем физику
        self.model.update(dt, cmds)

        # Получаем датчики с модели
        sensors = self.model.get_sensors()

        # Установка выходов
        if self.radio_controller.isChecked():
            combined_outputs = sensors.copy()
            for floor, time_left in self.cabin_panel.buttons_state.items():
                combined_outputs[f'btn_с{floor}'] = (time_left > 0)

            self.gpio.write_outputs(combined_outputs)

        # Отрисовываем
        self.view.update_ui(sensors)

        current_faults = self.model.get_faults()
        for fault in list(self.active_alarms.keys()):
            if fault not in current_faults:
                widget = self.active_alarms.pop(fault)
                widget.deleteLater()
        for fault in current_faults:
            if fault not in self.active_alarms:
                is_err = any(x in fault for x in ["КРИТ", "АВАРИЯ"])
                self.active_alarms[fault] = Toast(self, fault, is_error=is_err)

    def reset_simulator(self):
        self.model.velocity = 0
        self.model.position = self.model.FLOORS[1]  # Возврат на 1 этаж
        self.model.door_pos = 0  # Закрыть двери

        for fault_text in list(self.active_alarms.keys()):
            widget = self.active_alarms.pop(fault_text)
            widget.deleteLater()
        self.active_alarms.clear()

        self.radio_stop.setChecked(True)
        self.radio_d_stop.setChecked(True)
        self.radio_manual.setChecked(True)  # На всякий случай возвращаем в ручной режим

        self.view.update_ui(self.model.get_sensors())

        print("System Reset Performed")
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

        self.buttons_state = {1: 0.0, 2: 0.0, 3: 0.0}

        self.floor_units = {}

        for i in [3, 2, 1]:
            unit = ElevatorControlBlock(i)
            unit.btn.clicked.connect(lambda ch, f=i: self.press_button(f))
            self.floor_units[i] = unit
            main_layout.addWidget(unit)

        self.setLayout(main_layout)

    def press_button(self, floor):
        self.buttons_state[floor] = 0.2
        print(f"Кнопка {floor} нажата в UI, флаг взведен")

    def update_timers(self, dt):
        for floor in self.buttons_state:
            if self.buttons_state[floor] > 0:
                self.buttons_state[floor] -= dt
                if self.buttons_state[floor] < 0:
                    self.buttons_state[floor] = 0

if __name__ == "__main__":
    app = QApplication(sys.argv)
    sim = ElevatorSimulator()
    sim.resize(800, 600)
    sim.show()
    sys.exit(app.exec())