import logging
import time
import can

from enum import Enum
from typing import TypedDict, List, Optional, Union
from typing_extensions import Unpack

from multiprocessing import Process

import threading

from can_sdk.config import FrameValue, PrepareFrameParams, FrameValueKind, read as read_config

logger = logging.getLogger('sdk')
logging.basicConfig(level=logging.INFO)

class Connection:
    """
    Connection class that handles the connection to the CAN bus and provides a client to interact with it
    """
    def __init__(self, interface: str, channel: Union[str,int], bitrate: int) -> None:
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate

        self._config = read_config()


    def __enter__(self):
        self._bus = can.Bus(interface=self.interface, channel=self.channel, bitrate=self.bitrate)

        self.task_manager = SendingTaskManager(self._bus)
        self.task_manager.update_tasks((v, 0) for v in self._config)

        self.reader = CANBusReader(self._bus)
        self.reader.start()

        return _Client(self._bus, self.reader, self.task_manager)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.task_manager.stop_all()
        self.reader.stop()
        self._bus.shutdown()

    def options():
        """
        Returns a list of predefined connections
        """
        return [
            Connection(interface='kvaser', channel=0, bitrate=250000),
            Connection(interface='pcan', channel='PCAN_USBBUS1', bitrate=250000),
            Connection(interface='systec', channel='PCAN_USBBUS1', bitrate=250000),
            Connection(interface='ixxat', channel=0, bitrate=250000),
            Connection(interface='nican', channel='CAN0', bitrate=250000),
        ]


def prepare_frame(**kwargs: Unpack[PrepareFrameParams]) -> int:
    return (kwargs['priority'] << 26) | (kwargs.pop('data_page', 0) << 25) | (kwargs['pgn'] << 8) | kwargs.pop('source_addr', 0)

def compute_frame_value(v: FrameValue, raw_value: int) -> int:
    return int((raw_value - v['offset'] ) / v['factor'] * (10 ** v['dec']))

def compute_frame_values(vals: List[FrameValue], raw_vals: Optional[int]) -> int:
    base = 0xffffffffffffffff

    def to_little_endian(value: int, num_bits: int) -> int:
        """
        Converts the given value to little-endian format.
        Assumes `num_bits` is a multiple of 8.
        """
        le_value = 0
        for i in range(0, num_bits, 8):
            byte = (value >> i) & 0xff
            le_value |= byte << (num_bits - 8 - i)
        return le_value

    for val, raw_val in zip(vals, raw_vals):
        if val['kind'] == FrameValueKind.BINARY:
            raw_val = raw_val
        else:
            raw_val = compute_frame_value(val, raw_val)

        bit_index = val['bit_index']
        num_bits = val['num_bits']
        mask = (1 << num_bits) - 1  # Create a mask for the number of bits to use from raw_val

        if num_bits > 4:
            # Convert to little-endian if num_bits is more than 4
            # Ensure we're only working with the relevant bits from raw_val
            raw_val &= mask
            raw_val = to_little_endian(raw_val, num_bits)

        # Shift raw_val into the correct position
        raw_val <<= 64 - bit_index - num_bits

        # Apply mask to clear the area where raw_val will be placed
        base &= ~(mask << (64 - bit_index - num_bits))

        # Place raw_val into the correct position
        base |= raw_val

    return base

class SendingTaskManager:
    def __init__(self, bus):
        self.bus = bus
        self.active_tasks = {}  # {arbitration_id: (task, frame_info, raw_val)}
        self.lock = threading.Lock()

    def update_or_create_task(self, es_fv, raw_val):
        with self.lock:
            arbitration_id = prepare_frame(**es_fv['frame'])

            if arbitration_id in self.active_tasks:
                _, existing_es_fv, existing_raw_val = self.active_tasks[arbitration_id]

                if existing_es_fv != es_fv or existing_raw_val != raw_val:
                    # If the task exists but parameters have changed, stop the old task
                    self.active_tasks[arbitration_id][0].stop()
                    # Remove the old task before creating a new one
                    del self.active_tasks[arbitration_id]
                    # No need for an else branch to update, as stopping and recreating is required for changes

            # If the task does not exist or was just removed, create it
            if arbitration_id not in self.active_tasks:
                self._create_task(es_fv, raw_val)


    def update_tasks(self, values_to_send):
        with self.lock:
            seen_ids = set()

            for es_fv, raw_val in values_to_send:
                arbitration_id = prepare_frame(**es_fv['frame'])
                seen_ids.add(arbitration_id)

                if arbitration_id in self.active_tasks:
                    _, existing_frame_info, existing_raw_val = self.active_tasks[arbitration_id]
                    if existing_frame_info != es_fv['frame'] or existing_raw_val != raw_val:
                        # Frame info or raw value changed, recreate task
                        self.active_tasks[arbitration_id][0].stop()
                        self._create_task(es_fv, raw_val)
                else:
                    self._create_task(es_fv, raw_val)

            # Remove tasks that are no longer needed
            for arbitration_id in list(self.active_tasks.keys()):
                if arbitration_id not in seen_ids:
                    self.active_tasks[arbitration_id][0].stop()
                    del self.active_tasks[arbitration_id]

    def _create_task(self, es_fv, raw_val):
        # print(f"VAL: {es_fv}  RAW: {raw_val}")
        # print(hex(compute_frame_values([es_fv], [raw_val])))
        mess = can.Message(
            arbitration_id=prepare_frame(**es_fv['frame']),
            data=compute_frame_values([es_fv], [raw_val]).to_bytes(8, 'big'),
            is_extended_id=True
        )
        # print(es_fv)
        period = es_fv['frame']['period'] / 1000  # Convert milliseconds to seconds
        task = self.bus.send_periodic(mess, period)
        self.active_tasks[prepare_frame(**es_fv['frame'])] = (task, es_fv, raw_val)

    def stop_all(self):
        """Stops all active periodic sending tasks."""
        with self.lock:
            for arbitration_id, (task, _, _) in self.active_tasks.items():
                task.stop()
            self.active_tasks.clear()

class CANBusReader:
    def __init__(self, bus):
        self.bus = bus
        self.running = False
        self.read_thread = threading.Thread(target=self._read_messages, daemon=True)
        self.message_storage = {}  # Integrated storage for read messages
        self.storage_lock = threading.Lock()  # Protect access to message_storage

    def start(self):
        """Starts the message reading thread."""
        self.running = True
        print("Starting thread")
        self.read_thread.start()

    def stop(self):
        """Stops the message reading thread."""
        self.running = False
        self.read_thread.join()

    def _read_messages(self):
        """The method executed by the reading thread to continuously read messages."""
        while self.running:
            message = self.bus.recv(timeout=1.0)  # Adjust timeout as needed
            # print(message)
            if message:
                # Store the message in the integrated storage
                with self.storage_lock:
                    # Example storage structure: a list of messages for each arbitration ID
                    if message.arbitration_id not in self.message_storage:
                        self.message_storage[message.arbitration_id] = []
                    self.message_storage[message.arbitration_id].append(message)

    def get_messages(self, arbitration_id):
        """Retrieves stored messages for a given arbitration ID."""
        with self.storage_lock:
            return self.message_storage.get(arbitration_id, [])

    def clear_messages(self, arbitration_id=None):
        """Clears stored messages, either for a specific arbitration ID or all."""
        with self.storage_lock:
            if arbitration_id:
                if arbitration_id in self.message_storage:
                    del self.message_storage[arbitration_id]
            else:
                self.message_storage.clear()

    def cleanup_old_messages(self, max_age_seconds=5):
        """Removes messages that are older than max_age_seconds."""
        with self.storage_lock:
            current_time = time.time()
            for arbitration_id, messages in list(self.message_storage.items()):
                # Filter out messages newer than the max age
                self.message_storage[arbitration_id] = [
                    msg for msg in messages if current_time - msg.timestamp <= max_age_seconds
                ]

                # If this leaves the list empty, remove the arbitration ID entry entirely
                if not self.message_storage[arbitration_id]:
                    del self.message_storage[arbitration_id]


class _Client:
    """
    Client wrapper class that interacts with the CAN bus
    """
    def __init__(self, bus: can.Bus, reader: CANBusReader, task_mng: SendingTaskManager):
        self._bus = bus
        self._reader = reader
        self._task_mng = task_mng

        self._config = read_config()

    def read(self, index: int) -> Optional[int]:
        """
        Returns the last received value for given index (see can_sdk.config for more information on metrics)
        """

        val = next(x for x in self._config if x["id"] == index)

        arb_id = prepare_frame(**val['frame']) | 3

        msg = next(iter(self._reader.get_messages(arb_id)), None)

        if msg is not None:
            if arb_id == 0xc000003:
                print("AAAAA")
                print(msg.data)
                parsed_val = (int.from_bytes(msg.data, "little") & 0x00ffff0000) >> 16
                print(parsed_val)
            else:
                parsed_val = msg.data

            return parsed_val
        else:
            return None


    def write(self, index: int, value: int) -> bool:
        """
        Writes a value to the given index (see can_sdk.config for more information on metrics)
        """

        val = next(x for x in self._config if x["id"] == index)

        try:
            self._task_mng.update_or_create_task(val, value)
            return True
        except:
            return False

    def receiving(self, target_id: int, value: int, kind: str):
        if kind == "rx":
            self.write(target_id, value)
        elif kind == "tx":
            return self.read(target_id)
        return None


    def _send(self, msg: can.Message) -> bool:
        logger.debug(f"Message sent on {self._bus.channel_info}")
        try:
            self._bus.send(msg)
            return True
        except can.CanError:
            logger.error("Message NOT sent")
            return False

def main():
    logger.info("Initializing SDK")
    with Connection(interface='pcan', channel='PCAN_USBBUS1', bitrate=250000) as client:
        client.write(0, 1500)
        time.sleep(1)
        client.write(0, 1000)
        time.sleep(1)

        # print("READING 5")
        while True:
            client.read(5)
            time.sleep(200/1000)



        try:
            while True:
                time.sleep(5)
                client._reader.cleanup_old_messages()
        except KeyboardInterrupt:
            pass
    logger.info("SDK closed")

if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    # logging.getLogger('can').setLevel(logging.DEBUG)
    main()