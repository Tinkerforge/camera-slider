#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Starter Kit: Camera Slider Control
Copyright (C) 2015 Matthias Bolte <matthias@tinkerforge.com>

control.py: Control GUI for Starter Kit: Camera Slider

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

import sip
sip.setapi('QString', 2)
sip.setapi('QVariant', 2)

import os
import sys
import time
import signal

from PyQt4.QtCore import pyqtSignal, QObject, QTimer
from PyQt4.QtGui import QApplication, QMainWindow, QIcon, QMessageBox

from tinkerforge.ip_connection import IPConnection
from tinkerforge.brick_stepper import BrickStepper
from tinkerforge.bricklet_io4 import BrickletIO4
from tinkerforge.bricklet_industrial_quad_relay import BrickletIndustrialQuadRelay

from ui_mainwindow import Ui_MainWindow

CONTROL_VERSION = '1.0.0'

NO_STEPPER_BRICK_FOUND = 'No Stepper Brick found'
NO_IO4_BRICKLET_FOUND = 'No IO-4 Bricklet found'
NO_IQR_BRICKLET_FOUND = 'No Industrial Quad Relay Bricklet found'

DEVICE_IDENTIFIERS = {11: 'DC Brick',
                      13: 'Master Brick',
                      14: 'Servo Brick',
                      15: 'Stepper Brick',
                      16: 'IMU Brick',
                      17: 'RED Brick'}

TAB_CONNECTION = 0
TAB_CALIBRATION = 1
TAB_MOTION_CONTROL = 2
TAB_CAMERA_CONTROL = 3
TAB_ADVANCED_OPTIONS = 4

class SliderSpinSyncer(QObject):
    def __init__(self, parent, slider, spin, changed_callback):
        QObject.__init__(self, parent)

        self.slider = slider
        self.spin = spin
        self.changed_callback = changed_callback

        self.slider.valueChanged.connect(self.set_spinbox_from_slider_value)
        self.slider.sliderMoved.connect(self.set_spinbox_from_slider_position)
        self.spin.editingFinished.connect(self.set_slider_from_spinbox)

    def set_spinbox_from_slider_value(self):
        self.spin.setValue(self.slider.value())
        self.report_change()

    def set_spinbox_from_slider_position(self):
        self.spin.setValue(self.slider.sliderPosition())

    def set_slider_from_spinbox(self):
        self.slider.setValue(self.spin.value())
        self.report_change()

    def report_change(self):
        changed_callback = self.changed_callback

        if changed_callback != None:
            changed_callback()

class MainWindow(QMainWindow, Ui_MainWindow):
    qtcb_ipcon_enumerate = pyqtSignal(str, str, 'char', type((0,)), type((0,)), int, int)
    qtcb_ipcon_connected = pyqtSignal(int)
    qtcb_ipcon_disconnected = pyqtSignal(int)
    qtcb_stepper_position_reached = pyqtSignal(int)
    qtcb_stepper_new_state = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super(QMainWindow, self).__init__(parent)

        self.setupUi(self)
        self.setWindowTitle('Starter Kit: Camera Slider Control ' + CONTROL_VERSION)

        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        self.disconnect_times = []
        self.devices = {} # uid -> (connected_uid, device_identifier)

        self.maximum_positions = {} # uid -> maximum_position
        self.calibration_step = 0
        self.pending_minimum_position = 0

        self.stepper = None
        self.io4 = None
        self.iqr = None

        self.stepper_calibrated = False
        self.stepper_enabled = False

        self.qtcb_ipcon_enumerate.connect(self.cb_ipcon_enumerate)
        self.qtcb_ipcon_connected.connect(self.cb_ipcon_connected)
        self.qtcb_ipcon_disconnected.connect(self.cb_ipcon_disconnected)
        self.qtcb_stepper_position_reached.connect(self.cb_stepper_position_reached)
        self.qtcb_stepper_new_state.connect(self.cb_stepper_new_state)

        self.tab_widget.currentChanged.connect(lambda: self.update_ui_state())

        # create and setup ipcon
        self.ipcon = IPConnection()
        self.ipcon.register_callback(IPConnection.CALLBACK_ENUMERATE,
                                     self.qtcb_ipcon_enumerate.emit)
        self.ipcon.register_callback(IPConnection.CALLBACK_CONNECTED,
                                     self.qtcb_ipcon_connected.emit)
        self.ipcon.register_callback(IPConnection.CALLBACK_DISCONNECTED,
                                     self.qtcb_ipcon_disconnected.emit)

        # prepare connection tab
        self.button_connect.clicked.connect(self.connect_or_disconnect)

        # prepare calibration tab
        self.combo_stepper_uid.currentIndexChanged.connect(self.stepper_uid_changed)
        self.check_limit_switches.stateChanged.connect(lambda: self.update_ui_state())
        self.button_start_calibration.clicked.connect(self.start_calibration)
        self.button_abort_calibration.clicked.connect(self.abort_calibration)
        self.label_calibration_step_help.setVisible(False)

        # prepare motion control tab
        self.velocity_syncer = SliderSpinSyncer(self, self.slider_velocity, self.spin_velocity, self.velocity_changed)
        self.current_position_syncer = SliderSpinSyncer(self, self.slider_current_position, self.spin_current_position, None)
        self.target_position_syncer = SliderSpinSyncer(self, self.slider_target_position, self.spin_target_position, self.target_position_changed)

        self.button_stop_motion.clicked.connect(self.stop_motion)
        self.button_emergency_full_break.clicked.connect(self.emergency_full_break)

        self.current_position_timer = QTimer(self)
        self.current_position_timer.setInterval(50)
        self.current_position_timer.timeout.connect(self.update_current_position)

        # prepare camera control tab
        self.combo_iqr_uid.currentIndexChanged.connect(self.iqr_uid_changed)

        # prepare advanced options tab
        self.acceleration_syncer = SliderSpinSyncer(self, self.slider_acceleration, self.spin_acceleration, self.speed_ramping_changed)
        self.deceleration_syncer = SliderSpinSyncer(self, self.slider_deceleration, self.spin_deceleration, self.speed_ramping_changed)

        self.clear_all_uids()

    # override QMainWindow.closeEvent
    def closeEvent(self, event):
        self.disconnect()

    def shutdown(self, signal, frame):
        self.disconnect()

        print('Received SIGINT or SIGTERM, shutting down')

        sys.exit()

    def update_ui_state(self, connection_state=None):
        if connection_state == None:
            # FIXME: need to call processEvents() otherwise get_connection_state() might return the wrong value
            QApplication.processEvents()
            connection_state = self.ipcon.get_connection_state()

        connected = connection_state == IPConnection.CONNECTION_STATE_CONNECTED

        self.tab_widget.setTabEnabled(TAB_CALIBRATION, connected)
        self.tab_widget.setTabEnabled(TAB_MOTION_CONTROL, connected and self.stepper_calibrated)
        self.tab_widget.setTabEnabled(TAB_CAMERA_CONTROL, connected and self.stepper_calibrated)
        self.tab_widget.setTabEnabled(TAB_ADVANCED_OPTIONS, connected)

        # connection tab
        self.button_connect.setEnabled(True)

        if connection_state == IPConnection.CONNECTION_STATE_DISCONNECTED:
            self.button_connect.setText('Connect')
            self.edit_host.setEnabled(True)
            self.spin_port.setEnabled(True)
        elif connection_state == IPConnection.CONNECTION_STATE_CONNECTED:
            self.button_connect.setText('Disconnect')
            self.edit_host.setEnabled(False)
            self.spin_port.setEnabled(False)
        elif connection_state == IPConnection.CONNECTION_STATE_PENDING:
            self.button_connect.setText('Abort Pending Automatic Reconnect')
            self.edit_host.setEnabled(False)
            self.spin_port.setEnabled(False)

        # calibration tab
        stepper_uid = self.get_stepper_uid()
        io4_uid = self.get_io4_uid()
        found_stepper = stepper_uid != NO_STEPPER_BRICK_FOUND
        found_io4 = io4_uid != NO_IO4_BRICKLET_FOUND
        limit_switches = self.check_limit_switches.isChecked()

        self.combo_stepper_uid.setEnabled(found_stepper and self.calibration_step == 0 and not self.stepper_enabled)
        self.label_calibration_title.setVisible(found_stepper)
        self.label_calibration.setVisible(found_stepper)
        self.check_limit_switches.setEnabled(self.calibration_step == 0)
        self.combo_io4_uid.setEnabled(found_io4 and self.calibration_step == 0)
        self.button_start_calibration.setEnabled(found_stepper and (not limit_switches or found_io4) and (self.calibration_step != 0 or not self.stepper_enabled))

        if found_stepper:
            if stepper_uid not in self.maximum_positions:
                self.label_calibration.setText('Not calibrated')
            else:
                self.label_calibration.setText('Calibrated, {0} steps of movement range'.format(self.maximum_positions[stepper_uid]))

        self.label_io4_uid_title.setVisible(limit_switches)
        self.combo_io4_uid.setVisible(limit_switches)

        self.button_abort_calibration.setVisible(self.calibration_step != 0)
        self.label_calibration_step_help.setVisible(self.calibration_step != 0)

        if self.calibration_step == 1:
            self.button_start_calibration.setText('Set Minimum Position')

            if limit_switches:
                self.label_calibration_step_help.setText('FIXME')
            else:
                self.label_calibration_step_help.setText('Manually move the cart to the desired minimum position near the stepper motor then click the <b>Set Minimum Position</b> button to use that position as the new minimum position.')
        elif self.calibration_step == 2:
            self.button_start_calibration.setText('Drive Cart Forward')

            if limit_switches:
                self.label_calibration_step_help.setText('FIXME')
            else:
                self.label_calibration_step_help.setText('Click the <b>Drive Cart Forward</b> button to make the cart slowly drive away from the stepper motor. When the cart reaches the desired maximum position then click the <b>Stop Cart And Set Maximum Position</b> button to use that position as the new maximum position.')
        elif self.calibration_step == 3:
            self.button_start_calibration.setText('Stop Cart And Set Maximum Position')

            if limit_switches:
                self.label_calibration_step_help.setText('FIXME')
            else:
                self.label_calibration_step_help.setText('The cart is slowly driving away from the stepper motor. When the cart reaches the desired maximum position then click the <b>Stop Cart And Set Maximum Position</b> button to use that position as the new maximum position. Afterwards the calibration process is finished.')
        else:
            self.button_start_calibration.setText('Start Calibration')
            # FIXME: show hint that "start calibration" will abort pending motions

        # motion control tab
        self.slider_velocity.setEnabled(not self.stepper_enabled)
        self.spin_velocity.setEnabled(not self.stepper_enabled)
        self.slider_target_position.setEnabled(not self.stepper_enabled)
        self.spin_target_position.setEnabled(not self.stepper_enabled)
        self.button_stop_motion.setEnabled(self.stepper_enabled)
        self.button_emergency_full_break.setEnabled(self.stepper_enabled)

        # camera control tab

        # advanced options tab
        self.slider_acceleration.setEnabled(not self.stepper_enabled)
        self.spin_acceleration.setEnabled(not self.stepper_enabled)
        self.slider_deceleration.setEnabled(not self.stepper_enabled)
        self.spin_deceleration.setEnabled(not self.stepper_enabled)

    def update_current_position(self):
        if self.stepper != None and self.stepper_calibrated and self.calibration_step == 0:
            current_position = self.stepper.get_current_position()

            self.slider_current_position.setValue(current_position)

            if current_position == self.slider_target_position.value():
                self.disable_stepper()

    def connect_or_disconnect(self):
        connection_state = self.ipcon.get_connection_state()

        if connection_state == IPConnection.CONNECTION_STATE_DISCONNECTED:
            try:
                self.button_connect.setDisabled(True)
                self.button_connect.setText('Connecting ...')
                self.ipcon.connect(self.edit_host.text(), self.spin_port.value())
            except Exception as e:
                self.button_connect.setDisabled(False)
                self.button_connect.setText('Connect')

                QMessageBox.critical(self, 'Connection',
                                     'Could not connect. Please check host, check ' +
                                     'port and ensure that Brick Daemon is running.')
        else:
            self.disconnect()

    def disconnect(self):
        # FIXME: if stepper is still moving ask user about exiting then stop and disable stepper

        self.abort_calibration()

        try:
            self.ipcon.disconnect()
        except:
            pass

        self.clear_all_uids()

    def enable_stepper(self):
        if self.stepper_enabled:
            return

        if self.stepper != None:
            self.stepper.enable()

        self.stepper_enabled = True

        self.update_ui_state()

    def disable_stepper(self):
        if not self.stepper_enabled:
            return

        if self.stepper != None:
            self.stepper.disable()

        self.stepper_enabled = False

        self.update_ui_state()

    def start_calibration(self):
        if self.calibration_step == 0:
            # stop any motion in progress and clear current calibration
            self.disable_stepper()

            uid = self.get_stepper_uid()

            if uid != None:
                self.maximum_positions.pop(uid, None)
                self.stepper_calibrated = False

            self.calibration_step = 1
        elif self.calibration_step == 1:
            # set minimum position to zero
            self.stepper.set_current_position(0)

            self.calibration_step = 2
        elif self.calibration_step == 2:
            # drive forward slowly
            self.stepper.set_max_velocity(2000)
            self.stepper.set_speed_ramping(65535, 65535)
            self.enable_stepper()
            self.stepper.drive_forward()

            self.calibration_step = 3
        elif self.calibration_step == 3:
            # stop stepper motor. maximum position will be recorded in
            # new-state callback when stepper motor has really stopped
            self.stepper.stop()

        self.update_ui_state()

    def abort_calibration(self):
        if self.calibration_step == 0:
            return

        self.calibration_step = 0

        self.emergency_full_break()
        self.velocity_changed()
        self.speed_ramping_changed()
        self.update_ui_state()

    def stop_motion(self):
        if self.stepper != None and self.calibration_step == 0:
            self.stepper.stop()

    def emergency_full_break(self):
        if self.stepper != None and self.calibration_step == 0:
            self.stepper.full_brake() # FIXME: invalidate calibration?

    def get_stepper_uid(self):
        index = self.combo_stepper_uid.currentIndex()

        if index < 0:
            return None

        return self.combo_stepper_uid.itemData(index)

    def get_io4_uid(self):
        index = self.combo_io4_uid.currentIndex()

        if index < 0:
            return None

        return self.combo_io4_uid.itemData(index)

    def clear_all_uids(self):
        self.devices = {}

        self.combo_stepper_uid.clear()
        self.combo_stepper_uid.addItem(NO_STEPPER_BRICK_FOUND)

        self.combo_io4_uid.clear()
        self.combo_io4_uid.addItem(NO_IO4_BRICKLET_FOUND)

        self.combo_iqr_uid.clear()
        self.combo_iqr_uid.addItem(NO_IQR_BRICKLET_FOUND)

        self.update_ui_state()

    def stepper_uid_changed(self):
        self.current_position_timer.stop()

        if self.stepper != None:
            self.stepper.register_callback(BrickStepper.CALLBACK_POSITION_REACHED, None)
            self.stepper.register_callback(BrickStepper.CALLBACK_NEW_STATE, None)

        self.stepper = None
        self.stepper_calibrated = False
        uid = self.get_stepper_uid()

        if uid != None:
            self.stepper_calibrated = uid in self.maximum_positions

            if self.stepper_calibrated:
                maximum_position = self.maximum_positions[uid]

                self.slider_current_position.setMaximum(maximum_position)
                self.spin_current_position.setMaximum(maximum_position)
                self.slider_target_position.setMaximum(maximum_position)
                self.spin_target_position.setMaximum(maximum_position)

                self.label_current_position_unit.setText('of {0}'.format(maximum_position))
                self.label_target_position_unit.setText('of {0}'.format(maximum_position))

            self.stepper = BrickStepper(uid, self.ipcon)
            self.stepper.register_callback(BrickStepper.CALLBACK_POSITION_REACHED,
                                           self.qtcb_stepper_position_reached.emit)
            self.stepper.register_callback(BrickStepper.CALLBACK_NEW_STATE,
                                           self.qtcb_stepper_new_state.emit)

            self.velocity_changed()
            self.speed_ramping_changed()

            if uid in self.maximum_positions:
                current_position = self.stepper.get_current_position() # FIXME: blocking getter
                self.slider_target_position.setValue(current_position)

                self.update_current_position()
                self.current_position_timer.start()

        self.update_ui_state()

    def velocity_changed(self):
        if self.stepper != None and self.calibration_step == 0:
            self.stepper.set_max_velocity(self.slider_velocity.value())

    def target_position_changed(self):
        if self.stepper != None and self.stepper_calibrated and self.calibration_step == 0:
            current_position = self.stepper.get_current_position()
            target_position = self.slider_target_position.value()

            if current_position != target_position:
                self.enable_stepper()
                self.stepper.set_target_position(target_position)

    def iqr_uid_changed(self):
        self.iqr = None
        index = self.combo_iqr_uid.currentIndex()

        if index >= 0:
            uid = self.combo_iqr_uid.itemData(index)

            if uid != None:
                self.iqr = BrickletIndustrialQuadRelay(uid, self.ipcon)

        self.update_ui_state()

    def speed_ramping_changed(self):
        if self.stepper != None and self.calibration_step == 0:
            acceleration = self.slider_acceleration.value()
            deceleration = self.slider_deceleration.value()

            self.stepper.set_speed_ramping(acceleration, deceleration)

    def cb_ipcon_enumerate(self, uid, connected_uid, position,
                           hardware_version, firmware_version,
                           device_identifier, enumeration_type):
        if self.ipcon.get_connection_state() != IPConnection.CONNECTION_STATE_CONNECTED:
            # ignore enumerate callbacks that arrived after the connection got closed
            return

        if enumeration_type in [IPConnection.ENUMERATION_TYPE_AVAILABLE,
                                IPConnection.ENUMERATION_TYPE_CONNECTED]:
            self.devices[uid] = (connected_uid, device_identifier)

            def add_item(combo, no_device_text):
                if combo.itemText(0) == no_device_text:
                    combo.clear()

                if combo.findData(uid) < 0:
                    if connected_uid != '0':
                        if connected_uid in self.devices and self.devices[connected_uid][1] in DEVICE_IDENTIFIERS:
                            connected_name = DEVICE_IDENTIFIERS[self.devices[connected_uid][1]]
                        else:
                            connected_name = 'Unknown Brick'

                        text = '{0} @ {1} [{2}]'.format(uid, connected_name, connected_uid)
                    else:
                        text = uid

                    combo.addItem(text, uid)

            if device_identifier == BrickStepper.DEVICE_IDENTIFIER:
                add_item(self.combo_stepper_uid, NO_STEPPER_BRICK_FOUND)
            elif device_identifier == BrickletIO4.DEVICE_IDENTIFIER:
                add_item(self.combo_io4_uid, NO_IO4_BRICKLET_FOUND)
            elif device_identifier == BrickletIndustrialQuadRelay.DEVICE_IDENTIFIER:
                add_item(self.combo_iqr_uid, NO_IQR_BRICKLET_FOUND)

            if str(device_identifier).startswith('1'):
                def update_items(combo, expected_device_identifier):
                    for other_uid in self.devices:
                        other_connected_uid, other_device_identifier = self.devices[other_uid]

                        if other_device_identifier != expected_device_identifier:
                            continue

                        if other_connected_uid == uid and device_identifier in DEVICE_IDENTIFIERS:
                            connected_name = DEVICE_IDENTIFIERS[device_identifier]
                            text = '{0} @ {1} [{2}]'.format(other_uid, connected_name, uid)
                            index = combo.findData(other_uid)

                            if index >= 0:
                                combo.setItemText(index, text)

                update_items(self.combo_stepper_uid, BrickStepper.DEVICE_IDENTIFIER)
                update_items(self.combo_io4_uid, BrickletIO4.DEVICE_IDENTIFIER)
                update_items(self.combo_iqr_uid, BrickletIndustrialQuadRelay.DEVICE_IDENTIFIER)
        elif enumeration_type == IPConnection.ENUMERATION_TYPE_DISCONNECTED:
            # FIXME: abort calibration if stepper or io4 get disconnected

            self.devices.pop(uid, None)

            def remove_item(combo, no_device_text):
                index = combo.findData(uid)

                if index < 0:
                    return

                combo.removeItem(index)

                if combo.count() == 0:
                    combo.setEnabled(False)
                    combo.addItem(no_device_text)

            remove_item(self.combo_stepper_uid, NO_STEPPER_BRICK_FOUND)
            remove_item(self.combo_io4_uid, NO_IO4_BRICKLET_FOUND)
            remove_item(self.combo_iqr_uid, NO_IQR_BRICKLET_FOUND)

        self.update_ui_state()

    def cb_ipcon_connected(self, connect_reason):
        self.disconnect_times = []

        if connect_reason == IPConnection.CONNECT_REASON_REQUEST:
            self.ipcon.set_auto_reconnect(True)
            self.clear_all_uids()

        try:
            self.ipcon.enumerate()
        except:
            self.update_ui_state()

    def cb_ipcon_disconnected(self, disconnect_reason):
        if disconnect_reason == IPConnection.DISCONNECT_REASON_REQUEST or not self.ipcon.get_auto_reconnect():
            self.update_ui_state()
        elif len(self.disconnect_times) >= 3 and self.disconnect_times[-3] < time.time() + 1:
            self.disconnect_times = []
            self.ipcon.set_auto_reconnect(False)
            self.update_ui_state()

            QMessageBox.critical(self, 'Connection',
                                 'Stopped automatic reconnecting due to multiple connection errors in a row.')
        else:
            self.disconnect_times.append(time.time())
            self.update_ui_state(IPConnection.CONNECTION_STATE_PENDING)

    def cb_stepper_position_reached(self, position):
        if self.stepper != None:
            self.disable_stepper()

    def cb_stepper_new_state(self, state_new, state_previous):
        if self.stepper != None and state_new == BrickStepper.STATE_STOP:
            self.disable_stepper()

            if self.calibration_step == 3:
                maximum_position = self.stepper.get_current_position() # FIXME: blocking getter
                uid = self.get_stepper_uid()

                if uid != None:
                    self.maximum_positions[uid] = maximum_position

                self.abort_calibration()
                self.stepper_uid_changed()

class Application(QApplication):
    def __init__(self, args):
        super(QApplication, self).__init__(args)

        self.setWindowIcon(QIcon(os.path.join(get_resources_path(), 'control-icon.png')))

def get_program_path():
    # from http://www.py2exe.org/index.cgi/WhereAmI
    if hasattr(sys, 'frozen'):
        path = sys.executable
    else:
        path = __file__

    return os.path.dirname(os.path.realpath(unicode(path, sys.getfilesystemencoding())))

def get_resources_path():
    if sys.platform == 'darwin' and hasattr(sys, 'frozen'):
        return os.path.join(os.path.split(get_program_path())[0], 'Resources')
    else:
        return get_program_path()

def main():
    args = sys.argv

    if sys.platform == 'win32':
        args += ['-style', 'windowsxp']

    if sys.platform == 'darwin':
        # fix OSX 10.9 font
        # http://successfulsoftware.net/2013/10/23/fixing-qt-4-for-mac-os-x-10-9-mavericks/
        # https://bugreports.qt-project.org/browse/QTBUG-32789
        QFont.insertSubstitution('.Lucida Grande UI', 'Lucida Grande')
        # fix OSX 10.10 font
        # https://bugreports.qt-project.org/browse/QTBUG-40833
        QFont.insertSubstitution('.Helvetica Neue DeskInterface', 'Helvetica Neue')

    application = Application(args)

    main_window = MainWindow()
    main_window.show()

    sys.exit(application.exec_())

if __name__ == "__main__":
    main()
