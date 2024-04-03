import json

from enum import Enum
from typing import TypedDict

class FrameValueKind(Enum):
    BINARY = 1,
    ANALOG = 2

class FrameValueDirection(Enum):
    RX = 1,
    TX = 2


class PrepareFrameParams(TypedDict):
    pgn: int
    priority: int # number, 3 bits
    period: int # number, 3 bits
    data_page: int = 0
    source_addr: int = 0

class FrameValue(TypedDict):
    id: int
    name: str
    direction: str
    kind: FrameValueKind
    bit_index: int
    num_bits: int
    factor: int
    offset: int
    dec: int
    dim: str
    frame: PrepareFrameParams

def _create_frame_value(data: any) -> FrameValue:
    return FrameValue(
        id=data['id'],
        name=data['name'],
        frame=PrepareFrameParams(
            pgn=int(data['pgn'], 0),
            priority=data['prio'],
            period=data['period'],
        ),
        kind=FrameValueKind.BINARY if data['kindtype'] == 'binary' else FrameValueKind.ANALOG,
        direction=FrameValueDirection.RX if data['kind'] == 'rx' else FrameValueDirection.TX,
        bit_index=data['bitindex'],
        num_bits=data['numbits'],
        factor=data['factor'],
        offset=data['offset'],
        dec=data['dec'],
        dim=data['dim']
    )

def read() -> list[FrameValue]:
    with open('./config_system.json', 'r') as file:
        return list(map(_create_frame_value, json.load(file)))


if __name__ == '__main__':
    print(read())