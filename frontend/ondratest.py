import logging
import time
from can_sdk.client import Connection, Error

logger = logging.getLogger('sdk')

def main():
    logger.debug("Initializing SDK")

    with Connection(interface='pcan', channel='PCAN_USBBUS1', bitrate=250000) as client:
        client.write(0, 1000)
        client.read(0)

if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    logging.getLogger('can').setLevel(logging.DEBUG)
    main()