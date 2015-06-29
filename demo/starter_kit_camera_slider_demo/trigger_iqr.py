#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from time import sleep
from threading import Semaphore
from tinkerforge.ip_connection import IPConnection
from tinkerforge.bricklet_industrial_quad_relay import IndustrialQuadRelay

if __name__ == '__main__':
    try:
        host = sys.argv[1]
        port = int(sys.argv[2])
        uid = sys.argv[3]
        relay = int(sys.argv[4])
        trigger = int(sys.argv[5])
        wait = int(sys.argv[6])
    except:
        print('usage: {0} <host> <port> <iqr-uid> <relay> <trigger-duration> <wait-duration>'.format(sys.argv[0]))
        sys.exit(1)

    ipcon = IPConnection()
    iqr = IndustrialQuadRelay(uid, ipcon)
    sema = Semaphore(0)

    ipcon.connect(host, port)

    def monoflop_done(selection_mask, value_mask):
        sema.release()

    iqr.register_callback(iqr.CALLBACK_MONOFLOP_DONE, monoflop_done)
    iqr.set_monoflop(1 << relay, 1 << relay, trigger)

    sema.acquire()
    sleep(wait / 1000.0)

    ipcon.disconnect()
