import sys
import json
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import QTimer


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        self.mainLayout = QHBoxLayout()
        self.centralWidget.setLayout(self.mainLayout)

        self.valuesLayout = QVBoxLayout()
        self.mainLayout.addLayout(self.valuesLayout)

        with open('config_system.json', 'r') as file:
            self.data_system = json.load(file)  # Store this for later use

        self.all_system_objects = {item['id']: item for item in self.data_system}

        with open("config_user.json", "r") as file_user:
            self.data_user = json.load(file_user)

        # Dictionary to store label references
        self.label_references = {}

        for item in self.data_user["showed_ids"]:
            item_id = item['id']
            value = item['value']

            if item_id in self.all_system_objects:
                system_item = self.all_system_objects[item_id]
                label_text = f"{system_item['name']}: {value} {system_item.get('dim', 'No dimension')}"
                if system_item["kind"] == "rx":
                    label = QLabel(label_text)
                    self.valuesLayout.addWidget(label)
                    # Store the label with its ID for updates
                    self.label_references[item_id] = label

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_values)
        self.timer.start(100)  # Update interval in milliseconds

        self.setWindowTitle("Main Window")
        self.resize(400, 300)

    def update_values(self):
        with open("config_user.json", "r") as file_user:
            updated_data_user = json.load(file_user)

        for item in updated_data_user["showed_ids"]:
            item_id = int(item['id'])
            new_value = item['value']  # Assume new_value is the updated value you want to display

            if item_id in self.label_references:
                system_item = self.all_system_objects.get(item_id, {})
                updated_label_text = f"{system_item.get('name', 'Unknown')}: {new_value} {system_item.get('dim', 'No dimension')}"
                self.label_references[item_id].setText(updated_label_text)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
