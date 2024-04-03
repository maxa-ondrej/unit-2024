import logging
import time
import can
import j1939

import binascii

from sdk.sdk import mth

mth.haversine(1, 2, 3, 4)

logging.getLogger("j1939").setLevel(logging.DEBUG)
logging.getLogger("can").setLevel(logging.DEBUG)

def on_message(priority, pgn, sa, timestamp, data):
    """Receive incoming messages from the bus

    :param int priority:
        Priority of the message
    :param int pgn:
        Parameter Group Number of the message
    :param int sa:
        Source Address of the message
    :param int timestamp:
        Timestamp of the message
    :param bytearray data:
        Data of the PDU
    """
    # if (pgn == 0xf004 or pgn == 0xfedb or pgn == 0xfeee):
    print(f"{priority} {hex(pgn)} {sa} {timestamp}\t \t{" ".join(hex(b) for b in data)}")

def main():
    print("Initializing")

    # create the ElectronicControlUnit (one ECU can hold multiple ControllerApplications)
    ecu = j1939.ElectronicControlUnit()

    # Connect to the CAN bus
    # Arguments are passed to python-can's can.interface.Bus() constructor
    # (see https://python-can.readthedocs.io/en/stable/bus.html).
    # ecu.connect(bustype='socketcan', channel='can0')
    # ecu.connect(bustype='kvaser', channel=0, bitrate=250000)
    ecu.connect(bustype="pcan", channel="PCAN_USBBUS1", bitrate=250000)
    # ecu.connect(bustype="systec", channel="PCAN_USBBUS1", bitrate=250000)
    # ecu.connect(bustype='ixxat', channel=0, bitrate=250000)
    # ecu.connect(bustype='vector', app_name='CANalyzer', channel=0, bitrate=250000)
    # ecu.connect(bustype='nican', channel='CAN0', bitrate=250000)

    # ecu.add_ca(controller_application=ca)

    # subscribe to all (global) messages on the bus
    ecu.subscribe(on_message)

    time.sleep(120)

    print("Deinitializing")
    ecu.disconnect()



if __name__ == "__main__":
    main()
