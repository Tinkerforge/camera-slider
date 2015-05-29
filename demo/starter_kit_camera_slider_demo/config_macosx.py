# -*- coding: utf-8 -*-
"""
Starter Kit: Camera Slider Demo
Copyright (C) 2015 Matthias Bolte <matthias@tinkerforge.com>

config_macosx.py: Config Handling for Mac OSX

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
import plistlib
import os
import subprocess

CONFIG_FILENAME = os.path.expanduser('~/Library/Preferences/com.tinkerforge.starter_kit_camera_slider_demo.plist')
CONFIG_DIRNAME = os.path.dirname(CONFIG_FILENAME)

def get_plist_value(name, default):
    try:
        subprocess.call(['plutil', '-convert', 'xml1', CONFIG_FILENAME])
        return plistlib.readPlist(CONFIG_FILENAME)[name]
    except:
        return default

def set_plist_value(name, value):
    try:
        subprocess.call(['plutil', '-convert', 'xml1', CONFIG_FILENAME])
        root = plistlib.readPlist(CONFIG_FILENAME)
    except:
        root = {}

    root[name] = value

    if not os.path.exists(CONFIG_DIRNAME):
        os.makedirs(CONFIG_DIRNAME)

    plistlib.writePlist(root, CONFIG_FILENAME)

def get_strings(prefix, max_count):
    strings = []

    try:
        count = int(get_plist_value('{0}Count'.format(prefix), '-1'))
    except:
        count = max_count

    if count < 0 or count > max_count:
        count = max_count

    for i in range(count):
        string = get_plist_value('{0}{1}'.format(prefix, i), None)

        if string != None:
            strings.append(str(string))

    return strings

def set_strings(prefix, strings):
    i = 0

    for string in strings:
        set_plist_value('{0}{1}'.format(prefix, i), str(string))
        i += 1

    set_plist_value('{0}Count'.format(prefix), str(i))

def get_host_info_strings(max_count):
    return get_strings('HostInfo', max_count)

def set_host_info_strings(strings):
    set_strings('HostInfo', strings)

def get_stepper_info_strings(max_count):
    return get_strings('StepperInfo', max_count)

def set_stepper_info_strings(strings):
    set_strings('StepperInfo', strings)

def get_camera_trigger():
    return get_plist_value('CameraTrigger', DEFAULT_CAMERA_TRIGGER)

def set_camera_trigger(camera_trigger):
    set_plist_value('CameraTrigger', str(camera_trigger))
