import logging
import time
import can
import j1939
import os

from enum import Enum


from typing import TypedDict, List, Optional
from typing_extensions import Unpack

import threading

# Assuming prepare_frame and compute_frame_values are defined elsewhere



logging.getLogger('j1939').setLevel(logging.DEBUG)
logging.getLogger('can').setLevel(logging.DEBUG)

MY_ADDR = 0x03
MAX_PACKET_SIZE = 1785

# compose the name descriptor for the new ca
name = j1939.Name(
    arbitrary_address_capable=1,
    industry_group=j1939.Name.IndustryGroup.Industrial,
    vehicle_system_instance=1,
    vehicle_system=1,
    function=1,
    function_instance=1,
    ecu_instance=1,
    manufacturer_code=666,
    identity_number=1234567
    )

# create the ControllerApplications
ca = j1939.ControllerApplication(name, MY_ADDR)

def ca_receive(msg):

    # print('recev')

    # print(hex(pgn))
    # print(hex(source))

    print(hex(msg))

    # if pgn == 0x0000:
    #     print(f"{priority} {hex(pgn)} {source} {timestamp}\t \t{' '.join(hex(b) for b in data)}")

class FrameValueKind(Enum):
    BINARY = 1,
    ANALOG = 2


class PrepareFrameParams(TypedDict):
    pgn: int
    priority: int # number, 3 bits
    data_page: int = 0
    source_addr: int = 0


class FrameValue(TypedDict):
    id: int
    kind: FrameValueKind
    bit_index: int
    num_bits: int
    factor: int
    offset: int
    dec: int
    dim: str
    frame: PrepareFrameParams



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
        mess = can.Message(
            arbitration_id=prepare_frame(**es_fv['frame']),
            data=compute_frame_values([es_fv], [raw_val]).to_bytes(8, 'big'),
            is_extended_id=True
        )
        period = es_fv['frame']['period'] / 1000  # Convert to seconds
        task = self.bus.send_periodic(mess, period)
        self.active_tasks[prepare_frame(**es_fv['frame'])] = (task, es_fv['frame'], raw_val)

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
        self.read_thread.start()

    def stop(self):
        """Stops the message reading thread."""
        self.running = False
        self.read_thread.join()

    def _read_messages(self):
        """The method executed by the reading thread to continuously read messages."""
        while self.running:
            message = self.bus.recv(timeout=1.0)  # Adjust timeout as needed
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


def main():
    print("Initializing")
    op = PrepareFrameParams(
        pgn=0xfeef,
        priority=6,
        period=500
    )

    op_fv = FrameValue(
        kind=FrameValueKind.ANALOG,
        bit_index=24,
        num_bits=8,
        factor=4,
        offset=0,
        dec=2,
        dim='bar',
        frame=op
    )


    es = PrepareFrameParams(
        pgn=0xf004,
        priority=3,
        period=50
    )

    es_fv = FrameValue(
        kind=FrameValueKind.ANALOG,
        bit_index=24,
        num_bits=16,
        factor=0.125,
        offset=0,
        dec=0,
        dim='rpm',
        frame=es
    )

    ct = PrepareFrameParams(
        pgn=0xfeee,
        priority=6,
        period=1000
    )

    ct_fv = FrameValue(
        kind=FrameValueKind.ANALOG,
        bit_index=0,
        num_bits=8,
        factor=1,
        offset=-40,
        dec=0,
        dim='degC',
        frame=ct
    )

    lightd = PrepareFrameParams(
        pgn=0xfeca,
        priority=6,
        period=1000
    )

    al_fv = FrameValue(
        kind=FrameValueKind.BINARY,
        bit_index=2,
        num_bits=2,
        frame=lightd
    )

    rl_fv = FrameValue(
        kind=FrameValueKind.BINARY,
        bit_index=4,
        num_bits=2
    )

    values_to_send = [(es_fv, 1500)
                      , (al_fv, 1)
                      , (op_fv, 4)
                      ]

    with can.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=250000) as bus:
        task_manager = SendingTaskManager(bus)
        task_manager.update_tasks(values_to_send)

        reader = CANBusReader(bus)
        reader.start()

        try:
            while True:
                time.sleep(5)
                reader.cleanup_old_messages()
        except KeyboardInterrupt:
            task_manager.stop_all()



if __name__ == '__main__':
    main()