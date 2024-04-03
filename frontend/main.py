import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QBoxLayout, QFrame, QSpinBox, QLineEdit, QComboBox, QHBoxLayout
from can_sdk.client import Connection
from can_sdk.config import read as read_config, FrameValueDirection
import json

def divider():
    divider = QFrame()
    divider.setFrameShape(QFrame.HLine)
    return divider

def showed_ids():
    with open("config_user.json", "r") as file_user:
        data_user = json.load(file_user)
        return data_user["showed_ids"]

class ErrorWindow(QMainWindow):
    def __init__(self, message):
        super().__init__()
        self.setWindowTitle("Error")
        layout = QVBoxLayout()
        info_label = QLabel(message)
        closer = QPushButton("Close")
        closer.clicked.connect(self.close)

        layout.addWidget(info_label)
        layout.addWidget(closer)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

class ConfigWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configuration")
        layout = QVBoxLayout()
        info_label = QLabel("Configuration")
        closer = QPushButton("Close")
        closer.clicked.connect(self.close)

        # create two columns and put the label on the left and the button on the right
        column_layout = QBoxLayout(QBoxLayout.LeftToRight)
        column_layout.addWidget(info_label)
        column_layout.addWidget(closer)

        # create a dropdown for the user to select the interface
        interface_label = QLabel("Interface")


        available = Connection.options()

        interface_dropdown = QComboBox()

        # create new column layout and add two inputs for a string and one input for a number
        input_layout = QBoxLayout(QBoxLayout.LeftToRight)

        custom_label = QLabel("Or create a custom connection")

        input_1 = QLineEdit()
        input_2 = QLineEdit()
        input_3 = QSpinBox()
        input_3.setMinimum(0)
        input_3.setMaximum(1000000000)
        input_layout.addWidget(input_1)
        input_layout.addWidget(input_2)
        input_layout.addWidget(input_3)

        with open("config_user.json", "r") as file_user:
            data_user = json.load(file_user)
            bus_details = data_user["busDetails"]
            input_1.setText(bus_details["bustype"])
            input_2.setText(bus_details["channel"])
            input_3.setValue(bus_details["bitrate"])

        def setInputValues(index):
            if (index == -1):
                return
            connection = available[index]
            input_1.setText(connection.interface)
            input_2.setText(connection.channel)
            input_3.setValue(connection.bitrate)

        # make interface dropdown nullable
        interface_dropdown.setPlaceholderText("Select an interface")
        for connection in available:
            interface_dropdown.addItem(f"{connection.interface} {connection.channel} {connection.bitrate}")

        interface_dropdown.currentIndexChanged.connect(setInputValues)


        button_send = QPushButton("Connect")
        button_send.clicked.connect(lambda: self.openMainWindow(input_1.text(), input_2.text(), input_3.value()))

        layout.addLayout(column_layout)
        layout.addWidget(divider())
        layout.addWidget(interface_label)
        layout.addWidget(interface_dropdown)
        layout.addWidget(custom_label)
        layout.addLayout(input_layout)
        layout.addWidget(button_send)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def openMainWindow(self, bustype, channel, bitrate):
        if (bustype == "" or channel == "" or bitrate == 0):
            self.error_window = ErrorWindow("Please fill in all fields")
            self.error_window.show()
            return
        self.save_changes(bustype, channel, bitrate)
        self.main_window = MainWindow(bustype, channel, bitrate)
        self.main_window.show()
        self.close()

    def save_changes(self, bustype, channel, bitrate):
        # Update values in JSON file
        with open("config_user.json", "r") as file_user:
            data_user = json.load(file_user)
            bus_details = data_user["busDetails"]
            bus_details["bustype"] = bustype
            bus_details["channel"] = channel
            bus_details["bitrate"] = bitrate

        with open("config_user.json", "w") as file_user:
            json.dump(data_user, file_user)

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

class MainWindow(QMainWindow):
    def __init__(self, bustype, channel, bitrate):
        self.connection = Connection(bustype, channel, bitrate)
        self.client = self.connection.__enter__()

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

        column_layout = QBoxLayout(QBoxLayout.LeftToRight)
        info_label = QLabel("Dashboard")


        input_button = QPushButton("Send Values")
        input_button.clicked.connect(lambda: self.openInputWindow(self.client))

        column_layout.addWidget(info_label)
        column_layout.addWidget(input_button)

        layout.addLayout(column_layout)
        layout.addWidget(divider())

        with open('config_system.json', 'r') as file:
            data_system = json.load(file)

        # Convert system data to a dictionary for easier ID-based access
        all_system_objects = {item['id']: item for item in data_system}

        # Load JSON data from user configuration file
        with open("config_user.json", "r") as file_user:
            data_user = json.load(file_user)

        # Iterate over user-specified IDs and values
        for item in data_user["showed_ids"]:
            item_id = item['id']  # Convert ID to integer for matching
            value = item['value']

            # Check if the item ID exists in system configuration data
            if item_id in all_system_objects:
                system_item = all_system_objects[item_id]

                resultvalue = self.client.receiving(item_id, value, system_item["kind"])


                # Prepare the label text
                label_text = f"{system_item['name']}: {resultvalue} {system_item.get('dim', 'No dimension')}"

                # Create and add the label to the layout
                if system_item["kind"] == "tx":
                    label = QLabel(label_text)
                    layout.addWidget(label)
            else:
                print(f"Item with ID {item_id} not found in system configuration.")



        central_widget = QWidget()
        central_widget.setLayout(layout)

        self.setCentralWidget(central_widget)

    def openDetailWindow(self, name, value):
        self.detail_window = DetailWindow(name, value)
        self.detail_window.show()

    def openInputWindow(self, client):
        self.input_window = InputWindow(client)
        self.input_window.show()

class InputWindow(QMainWindow):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setWindowTitle("Input")
        layout = QVBoxLayout()
        info_label = QLabel("Input")
        closer = QPushButton("Close")
        closer.clicked.connect(self.close)

        # create two columns and put the label on the left and the button on the right
        column_layout = QBoxLayout(QBoxLayout.LeftToRight)
        column_layout.addWidget(info_label)
        column_layout.addWidget(closer)

        # create new column layout and add two inputs for a string and one input for a number
        input_layout = QBoxLayout(QBoxLayout.LeftToRight)

        self.add_combobox = QComboBox()

        self.filtered_frames = read_config()

        for showed_frame in showed_ids():
            self.filtered_frames = filter(lambda frame: frame["id"] != showed_frame["id"] and frame["direction"] == FrameValueDirection.RX, self.filtered_frames)

        self.filtered_frames = list(self.filtered_frames)

        for frame in self.filtered_frames:
            self.add_combobox.addItem(frame["name"], frame["id"])

        input_layout.addWidget(self.add_combobox)
        print(self.filtered_frames)


        add_button = QPushButton("Add")
        add_button.clicked.connect(lambda: self.add_value(self.filtered_frames[self.add_combobox.currentIndex()]["id"], 0))
        input_layout.addWidget(add_button)

        self.list_layout = QVBoxLayout()
        for frame in showed_ids():
            frame_id = frame["id"]
            frame_value = frame["value"]
            frame_name = next(filter(lambda frame: frame["id"] == frame_id, self.filtered_frames))["name"]
            frame_layout = QBoxLayout(QBoxLayout.LeftToRight)
            frame_label = QLabel(f"{frame_name}: {frame_value}")
            frame_layout.addWidget(frame_label)
            self.list_layout.addLayout(frame_layout)

        layout.addLayout(column_layout)
        layout.addWidget(divider())
        layout.addLayout(input_layout)
        layout.addWidget(divider())
        layout.addLayout(self.list_layout)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def add_value(self, id, value):
        with open("config_user.json", "r") as file_user:
            data_user = json.load(file_user)
            showed_ids = data_user["showed_ids"]
            showed_ids.append({"id": id, "value": value})

        with open("config_user.json", "w") as file_user:
            json.dump(data_user, file_user)

        for showed_frame in showed_ids:
            self.filtered_frames = filter(lambda frame: frame["id"] != showed_frame["id"] and frame["direction"] == FrameValueDirection.RX, self.filtered_frames)

        self.filtered_frames = list(self.filtered_frames)

        self.add_combobox.clear()

        for frame in self.filtered_frames:
            self.add_combobox.addItem(frame["name"], frame["id"])

        self.list_layout = QVBoxLayout()
        for frame in showed_ids():
            frame_id = frame["id"]
            frame_value = frame["value"]
            frame_name = next(filter(lambda frame: frame["id"] == frame_id, self.filtered_frames))["name"]
            frame_layout = QBoxLayout(QBoxLayout.LeftToRight)
            frame_label = QLabel(f"{frame_name}: {frame_value}")
            frame_layout.addWidget(frame_label)
            self.list_layout.addLayout(frame_layout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = ConfigWindow()
    main_window.show()
    sys.exit(app.exec())
