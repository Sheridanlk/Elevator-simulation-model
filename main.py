# main.py
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QCheckBox, \
    QGroupBox, QRadioButton, QFrame
from PyQt6.QtCore import QTimer
from elevator_model import ElevatorModel
from elevator_ui import ElevatorView, Toast


class ElevatorSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
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

        # Кабина
        lift_group = QGroupBox("Кабина")
        lift_layout = QVBoxLayout()
        self.radio_up = QRadioButton("Вверх")
        self.radio_stop = QRadioButton("Стоп")
        self.radio_down = QRadioButton("Вниз")
        self.radio_stop.setChecked(True)

        for r in [self.radio_up, self.radio_stop, self.radio_down]:
            lift_layout.addWidget(r)
        lift_group.setLayout(lift_layout)

        # Двери
        door_group = QGroupBox("Двери")
        door_layout = QVBoxLayout()
        self.radio_open = QRadioButton("Открыть")
        self.radio_d_stop = QRadioButton("Стоп")
        self.radio_close = QRadioButton("Закрыть")
        self.radio_d_stop.setChecked(True)

        for r in [self.radio_open, self.radio_d_stop, self.radio_close]:
            door_layout.addWidget(r)
        door_group.setLayout(door_layout)

        # Скорость кабины
        speed_group = QGroupBox("Скорость кабины")
        speed_layout = QVBoxLayout()
        self.radio_fast = QRadioButton("Нормальная")
        self.radio_slow = QRadioButton("Пониженная")
        self.radio_fast.setChecked(True)

        for r in [self.radio_fast, self.radio_slow]:
            speed_layout.addWidget(r)
        speed_group.setLayout(speed_layout)

        panel_layout.addWidget(lift_group)
        panel_layout.addWidget(speed_group)
        panel_layout.addWidget(door_group)


        # Запуск цикла (50 раз в секунду)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_simulation)
        self.timer.start(20)

    def update_simulation(self):
        dt = 0.02  # 20 миллисекунд

        # Читаем состояние кнопок
        cmds = {
            'up': self.radio_up.isChecked(),
            'down': self.radio_down.isChecked(),
            'low_speed': self.radio_slow.isChecked(),
            'open': self.radio_open.isChecked(),
            'close': self.radio_close.isChecked()
        }

        current_faults = self.model.get_faults()
        for fault in list(self.active_alarms.keys()):
            if fault not in current_faults:
                widget = self.active_alarms.pop(fault)
                widget.deleteLater()
        for fault in current_faults:
            if fault not in self.active_alarms:
                is_err = any(x in fault for x in ["КРИТ", "АВАРИЯ"])
                self.active_alarms[fault] = Toast(self, fault, is_error=is_err)

        # Считаем физику
        self.model.update(dt, cmds)
        # Получаем датчики
        sensors = self.model.get_sensors()
        # Отрисовываем
        self.view.update_ui(sensors)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    sim = ElevatorSimulator()
    sim.resize(800, 600)
    sim.show()
    sys.exit(app.exec())