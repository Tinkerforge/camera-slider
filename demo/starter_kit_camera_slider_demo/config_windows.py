# -*- coding: utf-8 -*-
"""
Starter Kit: Camera Slider Demo
Copyright (C) 2015 Matthias Bolte <matthias@tinkerforge.com>

config_windows.py: Config Handling for Windows

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

import winreg

KEY_NAME = 'Software\\Tinkerforge\\Starter Kit Camera Slider Demo'

def get_registry_value(name, default):
    try:
        reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_NAME)
    except WindowsError:
        return default
    else:
        try:
            return winreg.QueryValueEx(reg, name)[0]
        except:
            return default
        finally:
            winreg.CloseKey(reg)

def set_registry_value(name, type_, value):
    try:
        reg = winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY_NAME)
    except WindowsError:
        logging.warn('Could not create registry key: HKCU\\{0}'.format(KEY_NAME))
    else:
        try:
            winreg.SetValueEx(reg, name, 0, type_, value)
        except:
            logging.warn('Could not set registry value: HKCU\\{0}\\{1}'.format(KEY_NAME, name))
        finally:
            winreg.CloseKey(reg)

def get_strings(prefix, max_count):
    strings = []

    try:
        count = int(get_registry_value('{0}Count'.format(prefix), '-1'))
    except:
        count = max_count

    if count < 0 or count > max_count:
        count = max_count

    for i in range(count):
        string = get_registry_value('{0}{1}'.format(prefix, i), None)

        if string != None:
            strings.append(str(string))

    return strings

def set_strings(prefix, strings):
    i = 0

    for string in strings:
        set_registry_value('{0}{1}'.format(prefix, i), winreg.REG_SZ, str(string))
        i += 1

    set_registry_value('{0}Count'.format(prefix), winreg.REG_SZ, str(i))

def get_host_info_strings(max_count):
    return get_strings('HostInfo', max_count)

def set_host_info_strings(strings):
    set_strings('HostInfo', strings)

def get_stepper_info_strings(max_count):
    return get_strings('StepperInfo', max_count)

def set_stepper_info_strings(strings):
    set_strings('StepperInfo', strings)

def get_camera_trigger():
    return get_registry_value('CameraTrigger', DEFAULT_CAMERA_TRIGGER)

def set_camera_trigger(camera_trigger):
    set_registry_value('CameraTrigger', winreg.REG_SZ, str(camera_trigger))
