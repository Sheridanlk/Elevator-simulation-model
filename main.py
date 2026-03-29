# main.py
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QCheckBox, \
    QGroupBox, QRadioButton, QFrame
from PyQt6.QtCore import QTimer
from elevator_model import ElevatorModel
from elevator_ui import ElevatorView, Toast
from gpio_handler import GPIOHandler


class ElevatorSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.gpio = GPIOHandler()
        self.setWindowTitle("Лифт-Симулятор ПЛК")
        #self.setStyleSheet("background-color: #1e1e1e; color: #ecf0f1;")
        self.active_alarms = {}

        self.model = ElevatorModel()
        self.view = ElevatorView(self.model)

        # Сборка интерфейса
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)


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

        self.btn_reset = QPushButton("СБРОС СИСТЕМЫ (RESET)")
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
            cmds = self.gpio.read_inputs()


        # Считаем физику
        self.model.update(dt, cmds)

        # Получаем датчики
        sensors = self.model.get_sensors()

        if self.radio_controller:
            self.gpio.write_outputs(sensors)

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    sim = ElevatorSimulator()
    sim.resize(800, 600)
    sim.show()
    sys.exit(app.exec())