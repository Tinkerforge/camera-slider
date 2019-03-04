# -*- coding: utf-8 -*-
"""
Starter Kit: Camera Slider Demo
Copyright (C) 2015 Matthias Bolte <matthias@tinkerforge.com>

config_linux.py: Config Handling for Linux

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

from starter_kit_camera_slider_demo.config_common import *
import os

import configparser

XDG_CONFIG_HOME = os.getenv('XDG_CONFIG_HOME')

if XDG_CONFIG_HOME is None or len(XDG_CONFIG_HOME) < 1:
    CONFIG_FILENAME = os.path.expanduser('~/.config/Tinkerforge/starter_kit_camera_slider_demo.conf')
else:
    CONFIG_FILENAME = os.path.join(XDG_CONFIG_HOME, 'Tinkerforge/starter_kit_camera_slider_demo.conf')

CONFIG_DIRNAME = os.path.dirname(CONFIG_FILENAME)

def get_config_value(section, option, default):
    scp = configparser.SafeConfigParser()
    scp.read(CONFIG_FILENAME)

    try:
        return scp.get(section, option)
    except configparser.Error:
        return default

def set_config_value(section, option, value):
    scp = configparser.SafeConfigParser()
    scp.read(CONFIG_FILENAME)

    if not scp.has_section(section):
        scp.add_section(section)

    scp.set(section, option, value)

    if not os.path.exists(CONFIG_DIRNAME):
        os.makedirs(CONFIG_DIRNAME)

    with open(CONFIG_FILENAME, 'w') as f:
        scp.write(f)

def get_strings(category, prefix, max_count):
    strings = []

    try:
        count = int(get_config_value(category, '{0}Count'.format(prefix), '-1'))
    except:
        count = max_count

    if count < 0 or count > max_count:
        count = max_count

    for i in range(count):
        string = get_config_value(category, '{0}{1}'.format(prefix, i), None)

        if string != None:
            strings.append(str(string))

    return strings

def set_strings(category, prefix, strings):
    i = 0

    for string in strings:
        set_config_value(category, '{0}{1}'.format(prefix, i), str(string))
        i += 1

    set_config_value(category, '{0}Count'.format(prefix), str(i))

def get_host_info_strings(max_count):
    return get_strings('Connection', 'HostInfo', max_count)

def set_host_info_strings(strings):
    set_strings('Connection', 'HostInfo', strings)

def get_stepper_info_strings(max_count):
    return get_strings('Calibration', 'StepperInfo', max_count)

def set_stepper_info_strings(strings):
    set_strings('Calibration', 'StepperInfo', strings)

def get_camera_trigger():
    return get_config_value('TimeLapse', 'CameraTrigger', DEFAULT_CAMERA_TRIGGER)

def set_camera_trigger(camera_trigger):
    set_config_value('TimeLapse', 'CameraTrigger', str(camera_trigger))
