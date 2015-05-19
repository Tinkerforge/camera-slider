# -*- coding: utf-8 -*-
"""
Starter Kit: Camera Slider Demo
Copyright (C) 2015 Matthias Bolte <matthias@tinkerforge.com>

config.py: Config Handling

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public
License along with this program; if not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.
"""

import sys
from starter_kit_camera_slider_demo.config_common import *

class HostInfo(object):
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    use_authentication = DEFAULT_USE_AUTHENTICATION
    secret = DEFAULT_SECRET
    remember_secret = DEFAULT_REMEMBER_SECRET

def get_host_info_strings(): return [DEFAULT_HOST_INFO]
def set_host_info_strings(host_info_strings): pass

class StepperInfo(object):
    uid = None
    minimum_position = 0
    maximum_position = 0
    current_position = 0

    @property
    def motion_range(self):
        return abs(self.maximum_position - self.minimum_position)

def get_stepper_info_strings(): return []
def set_stepper_info_strings(stepper_info_strings): pass

if sys.platform.startswith('linux') or sys.platform.startswith('freebsd'):
    from starter_kit_camera_slider_demo.config_linux import *
elif sys.platform == 'darwin':
    from starter_kit_camera_slider_demo.config_macosx import *
elif sys.platform == 'win32':
    from starter_kit_camera_slider_demo.config_windows import *
else:
    print("Unsupported platform: " + sys.platform)

def get_host_infos(count):
    host_infos = []

    for host_info_string in get_host_info_strings(count):
        # host|port|use_authentication|remember_secret|secret
        parts = host_info_string.split('|', 5)

        if len(parts) != 5:
            continue

        try:
            host_info = HostInfo()

            host_info.host = parts[0]
            host_info.port = int(parts[1])
            host_info.use_authentication = bool(int(parts[2]))
            host_info.secret = parts[4]
            host_info.remember_secret = bool(int(parts[3]))

            if not host_info.remember_secret:
                host_info.secret = DEFAULT_SECRET

            host_infos.append(host_info)
        except:
            continue

        if len(host_infos) == count:
            break

    if len(host_infos) == 0:
        host_infos.append(HostInfo())

    return host_infos

def set_host_infos(host_infos):
    host_info_strings = []

    for host_info in host_infos:
        use_authentication = 0
        remember_secret = 0
        secret = DEFAULT_SECRET

        if host_info.use_authentication:
            use_authentication = 1

        if host_info.remember_secret:
            remember_secret = 1
            secret = host_info.secret

        # host|port|use_authentication|remember_secret|secret
        host_info_string = '{0}|{1}|{2}|{3}|{4}'.format(host_info.host,
                                                        host_info.port,
                                                        use_authentication,
                                                        remember_secret,
                                                        secret)

        host_info_strings.append(host_info_string)

    set_host_info_strings(host_info_strings)

def get_stepper_infos(count):
    stepper_infos = []

    for stepper_info_string in get_stepper_info_strings(count):
        # uid|minimum_position|maximum_position|current_position
        parts = stepper_info_string.split('|', 4)

        if len(parts) != 4:
            continue

        try:
            stepper_info = StepperInfo()

            stepper_info.uid = parts[0]
            stepper_info.minimum_position = int(parts[1])
            stepper_info.maximum_position = int(parts[2])
            stepper_info.current_position = int(parts[3])

            stepper_infos.append(stepper_info)
        except:
            continue

        if len(stepper_infos) == count:
            break

    return stepper_infos

def set_stepper_infos(stepper_infos):
    stepper_info_strings = []

    for stepper_info in stepper_infos:
        # uid|minimum_position|maximum_position|current_position
        stepper_info_string = '{0}|{1}|{2}|{3}'.format(stepper_info.uid,
                                                       stepper_info.minimum_position,
                                                       stepper_info.maximum_position,
                                                       stepper_info.current_position)

        stepper_info_strings.append(stepper_info_string)

    set_stepper_info_strings(stepper_info_strings)
