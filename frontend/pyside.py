import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QBoxLayout, QFrame, QSpinBox, QLineEdit

class DetailWindow(QMainWindow):
    def __init__(self, name, value):
        super().__init__()
        self.setWindowTitle(f"Detail for {name}")
        layout = QVBoxLayout()
        info_label = QLabel(f"{name}: {value}")
        layout.addWidget(info_label)
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Settings")
        layout = QVBoxLayout()
        info_label = QLabel("Settings")
        closer = QPushButton("Close")
        closer.clicked.connect(self.close)

        # create two columns and put the label on the left and the button on the right
        column_layout = QBoxLayout(QBoxLayout.LeftToRight)
        column_layout.addWidget(info_label)
        column_layout.addWidget(closer)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)

        # create new column layout and add two inputs for a string and one input for a number
        input_layout = QBoxLayout(QBoxLayout.LeftToRight)

        input_1 = QLineEdit()
        input_2 = QLineEdit()
        input_3 = QSpinBox()
        input_layout.addWidget(input_1)
        input_layout.addWidget(input_2)
        input_layout.addWidget(input_3)

        layout.addLayout(column_layout)
        layout.addWidget(divider)
        layout.addLayout(input_layout)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dashboard")

        # Values for demonstration
        self.values = {
            "Value 1": 123,
            "Value 2": 456,
            "Value 3": 789,
            "Value 4": 101
        }

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(lambda: self.openSettings())
        layout.addWidget(settings_button)

        for name, value in self.values.items():
            label = QLabel(f"{name}: {value}")
            button = QPushButton(f"Open {name}")
            button.clicked.connect(lambda n=name, v=value: self.openDetailWindow(n, v))
            layout.addWidget(label)
            layout.addWidget(button)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def openDetailWindow(self, name, value):
        self.detail_window = DetailWindow(name, value)
        self.detail_window.show()

    def openSettings(self):
        self.settings_window = SettingsWindow()
        self.settings_window.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())
