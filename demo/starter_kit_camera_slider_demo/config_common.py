# -*- coding: utf-8 -*-
"""
Starter Kit: Camera Slider Demo
Copyright (C) 2015 Matthias Bolte <matthias@tinkerforge.com>

config_common.py: Common Config Handling

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

DEMO_VERSION = '1.0.1'

HOST_INFO_COUNT = 1
STEPPER_INFO_COUNT = 100

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 4223

DEFAULT_USE_AUTHENTICATION = False
DEFAULT_SECRET = ''
DEFAULT_REMEMBER_SECRET = False

# host|port|use_authentication|remember_secret|secret
DEFAULT_HOST_INFO = 'localhost|4223|0|0|'

DEFAULT_CAMERA_TRIGGER = 'gphoto2 --capture-image'
