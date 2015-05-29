#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from time import sleep
from threading import Semaphore
from tinkerforge.ip_connection import IPConnection
from tinkerforge.bricklet_piezo_speaker import PiezoSpeaker

if __name__ == '__main__':
    try:
        host = sys.argv[1]
        port = int(sys.argv[2])
        uid = sys.argv[3]
        frequency = int(sys.argv[4])
        trigger = int(sys.argv[5])
        wait = int(sys.argv[6])
    except:
        print('usage: {0} <host> <port> <ps-uid> <frequency> <trigger-duration> <wait-duration>'.format(sys.argv[0]))
        sys.exit(1)

    ipcon = IPConnection()
    ps = PiezoSpeaker(uid, ipcon)
    sema = Semaphore(0)

    ipcon.connect(host, port)

    def beep_finished():
        sema.release()

    ps.register_callback(ps.CALLBACK_BEEP_FINISHED, beep_finished)
    ps.beep(trigger, frequency)

    sema.acquire()
    sleep(wait / 1000.0)

    ipcon.disconnect()
