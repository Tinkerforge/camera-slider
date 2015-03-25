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

from ui_mainwindow import Ui_MainWindow

CONTROL_VERSION = '1.0.0'

NO_STEPPER_BRICK_FOUND = 'No Stepper Brick found'
NO_IO4_BRICKLET_FOUND = 'No IO-4 Bricklet found'

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
        self.calibration_in_progress = False
        self.temporary_minimum_position = None
        self.temporary_maximum_position = None

        self.stepper = None
        self.io4 = None

        self.stepper_calibrated = False
        self.stepper_enabled = False
        self.stepper_driving = False
        self.stepper_reversed = False

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
        self.check_automatic_power_control.stateChanged.connect(self.automatic_power_control_changed)
        self.check_limit_switches.stateChanged.connect(lambda: self.update_ui_state())
        self.button_calibration_start.clicked.connect(self.calibration_start)
        self.button_calibration_abort.clicked.connect(self.calibration_abort)
        self.button_calibration_forward.pressed.connect(self.calibration_forward_pressed)
        self.button_calibration_forward.released.connect(self.calibration_forward_released)
        self.button_calibration_backward.pressed.connect(self.calibration_backward_pressed)
        self.button_calibration_backward.released.connect(self.calibration_backward_released)
        self.button_calibration_set_minimum.clicked.connect(self.calibration_set_minimum)
        self.button_calibration_set_maximum.clicked.connect(self.calibration_set_maximum)

        # prepare motion control tab
        self.velocity_syncer = SliderSpinSyncer(self, self.slider_velocity, self.spin_velocity, self.velocity_changed)
        self.current_position_syncer = SliderSpinSyncer(self, self.slider_current_position, self.spin_current_position, None)
        self.target_position_syncer = SliderSpinSyncer(self, self.slider_target_position, self.spin_target_position, self.target_position_changed)

        self.button_stop_motion.clicked.connect(self.stop_motion)
        #self.button_emergency_full_break.clicked.connect(self.emergency_full_break) # FIXME

        self.current_position_timer = QTimer(self)
        self.current_position_timer.setInterval(50)
        self.current_position_timer.timeout.connect(self.update_current_position)

        # prepare camera control tab

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
        self.tab_widget.setTabEnabled(TAB_CAMERA_CONTROL, connected and self.stepper_calibrated and False) # FIXME
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
        limit_switches = self.check_limit_switches.isChecked()
        automatic_power_control = self.check_automatic_power_control.isChecked()

        self.combo_stepper_uid.setEnabled(stepper_uid != None and not self.calibration_in_progress and not self.stepper_enabled)
        self.check_automatic_power_control.setEnabled(not self.calibration_in_progress and not self.stepper_driving)
        self.check_limit_switches.setEnabled(not self.calibration_in_progress and False) # FIXME
        self.label_io4_uid_title.setVisible(limit_switches)
        self.combo_io4_uid.setVisible(limit_switches)
        self.combo_io4_uid.setEnabled(io4_uid != None and not self.calibration_in_progress)
        self.button_calibration_start.setEnabled(stepper_uid != None and \
                                                 (not limit_switches or io4_uid != None) and \
                                                 (not self.calibration_in_progress or \
                                                  (self.temporary_minimum_position != None and \
                                                   self.temporary_maximum_position != None)) and \
                                                 not self.stepper_driving)
        self.button_calibration_abort.setEnabled(self.calibration_in_progress and not self.stepper_driving)
        self.label_calibration_help1.setVisible(stepper_uid != None)
        self.line_calibration_motion.setVisible(self.calibration_in_progress)
        self.button_calibration_forward.setVisible(self.calibration_in_progress)
        self.button_calibration_forward.setEnabled(not self.button_calibration_backward.isDown())
        self.button_calibration_backward.setVisible(self.calibration_in_progress)
        self.button_calibration_backward.setEnabled(not self.button_calibration_forward.isDown())
        self.button_calibration_set_minimum.setVisible(self.calibration_in_progress)
        self.button_calibration_set_minimum.setEnabled(not self.stepper_driving)
        self.button_calibration_set_maximum.setVisible(self.calibration_in_progress)
        self.button_calibration_set_maximum.setEnabled(not self.stepper_driving)
        self.label_calibration_help2.setVisible(self.calibration_in_progress)

        if self.calibration_in_progress:
            self.button_calibration_start.setText('Apply Calibration')
            self.label_calibration_help1.setText('Set the desired minimum and maximum position using the buttons below. Afterwards click the <b>Apply Calibration</b> button to use the new calibration.')
        elif stepper_uid != None:
            if stepper_uid not in self.maximum_positions:
                self.button_calibration_start.setText('Start Calibration')
                self.label_calibration_help1.setText('The selected Stepper Brick [<b>{0}</b>] is <b>not</b> calibrated. Click the <b>Start Calibration</b> button to calibrate the selected Stepper Brick.'.format(stepper_uid))
            else:
                self.button_calibration_start.setText('Start Recalibration')
                self.label_calibration_help1.setText('The selected Stepper Brick [<b>{0}</b>] is calibrated. It has <b>{1}</b> steps of motion range. If the cart was manually moved since the last calibration, then click the <b>Start Recalibration</b> button to recalibrate the selected Stepper Brick.'.format(stepper_uid, abs(self.maximum_positions[stepper_uid])))
        else:
            self.button_calibration_start.setText('Start Calibration')
            self.label_calibration_help1.setText('')

        if self.temporary_minimum_position == None:
            self.button_calibration_set_minimum.setText('Set Minimum')
        else:
            self.button_calibration_set_minimum.setText('Set Minimum Again')

        if self.temporary_maximum_position == None:
            self.button_calibration_set_maximum.setText('Set Maximum')
        else:
            self.button_calibration_set_maximum.setText('Set Maximum Again')

        # motion control tab
        self.slider_velocity.setEnabled(not self.stepper_driving)
        self.spin_velocity.setEnabled(not self.stepper_driving)
        self.slider_target_position.setEnabled(not self.stepper_driving)
        self.spin_target_position.setEnabled(not self.stepper_driving)
        self.button_stop_motion.setEnabled(self.stepper_driving)
        self.button_emergency_full_break.setEnabled(self.stepper_driving and False) # FIXME

        # camera control tab

        # advanced options tab
        self.slider_acceleration.setEnabled(not self.stepper_driving)
        self.spin_acceleration.setEnabled(not self.stepper_driving)
        self.slider_deceleration.setEnabled(not self.stepper_driving)
        self.spin_deceleration.setEnabled(not self.stepper_driving)

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

        self.update_ui_state()

    def prepare_stepper_motion(self):
        if self.stepper_driving:
            return

        if self.stepper != None and self.check_automatic_power_control.isChecked():
            self.stepper.enable()
            self.stepper_enabled = True

        self.stepper_driving = True
        self.update_ui_state()

    def stepper_motion_stopped(self):
        if not self.stepper_driving:
            return

        if self.stepper != None and self.check_automatic_power_control.isChecked():
            self.stepper.disable()
            self.stepper_enabled = False

        self.stepper_driving = False
        self.update_ui_state()

    def update_current_position(self):
        if self.stepper != None and self.stepper_calibrated and not self.calibration_in_progress:
            current_position = abs(self.stepper.get_current_position())
            self.slider_current_position.setValue(current_position)

            if current_position == self.slider_target_position.value():
                self.stepper_motion_stopped()

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
        # FIXME: if stepper is still moving ask user about exiting, then stop and disable stepper

        self.calibration_abort()

        try:
            self.ipcon.disconnect()
        except:
            pass

        self.clear_all_uids()

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
                self.stepper_reversed = maximum_position < 0
                maximum_position = abs(maximum_position)

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

    def automatic_power_control_changed(self):
        if self.stepper != None:
            if self.check_automatic_power_control.isChecked():
                self.stepper.disable()
                self.stepper_enabled = False
            else:
                self.stepper.enable()
                self.stepper_enabled = True

            self.update_ui_state()

    def calibration_start(self):
        if not self.calibration_in_progress:
            uid = self.get_stepper_uid()

            if uid != None:
                self.maximum_positions.pop(uid, None)
                self.stepper_calibrated = False

            self.calibration_in_progress = True
            self.temporary_minimum_position = None
            self.temporary_maximum_position = None
        elif self.temporary_minimum_position != None and self.temporary_maximum_position != None:
            uid = self.get_stepper_uid()

            if uid != None:
                self.maximum_positions[uid] = self.temporary_maximum_position - self.temporary_minimum_position
                new_current_position = self.stepper.get_current_position() - self.temporary_minimum_position
                self.stepper.set_current_position(new_current_position)

            self.calibration_abort()
            self.stepper_uid_changed()

        self.update_ui_state()

    def calibration_abort(self):
        if not self.calibration_in_progress:
            return

        self.calibration_in_progress = False
        self.temporary_minimum_position = None
        self.temporary_maximum_position = None

        self.stop_motion()
        self.velocity_changed()
        self.speed_ramping_changed()
        self.update_ui_state()

    def calibration_forward_pressed(self):
        if self.stepper != None and self.calibration_in_progress:
            self.stepper.set_max_velocity(2000)
            self.stepper.set_speed_ramping(65535, 65535)
            self.prepare_stepper_motion()
            self.stepper.drive_forward()

    def calibration_forward_released(self):
        if self.stepper != None and self.calibration_in_progress:
            self.stepper.stop()

    def calibration_backward_pressed(self):
        if self.stepper != None and self.calibration_in_progress:
            self.stepper.set_max_velocity(2000)
            self.stepper.set_speed_ramping(65535, 65535)
            self.prepare_stepper_motion()
            self.stepper.drive_backward()

    def calibration_backward_released(self):
        if self.stepper != None and self.calibration_in_progress:
            self.stepper.stop()

    def calibration_set_minimum(self):
        if self.stepper != None and self.calibration_in_progress and not self.stepper_driving:
            self.temporary_minimum_position = self.stepper.get_current_position()
            self.update_ui_state()

    def calibration_set_maximum(self):
        if self.stepper != None and self.calibration_in_progress and not self.stepper_driving:
            self.temporary_maximum_position = self.stepper.get_current_position()
            self.update_ui_state()

    def velocity_changed(self):
        if self.stepper != None and not self.calibration_in_progress:
            self.stepper.set_max_velocity(self.slider_velocity.value())

    def target_position_changed(self):
        if self.stepper != None and self.stepper_calibrated and not self.calibration_in_progress:
            current_position = self.stepper.get_current_position()
            target_position = self.slider_target_position.value()

            if self.stepper_reversed:
                target_position = -target_position

            if current_position != target_position:
                self.prepare_stepper_motion()
                self.stepper.set_target_position(target_position)

    def stop_motion(self):
        if self.stepper != None and not self.calibration_in_progress:
            self.stepper.stop()

    def speed_ramping_changed(self):
        if self.stepper != None and not self.calibration_in_progress:
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
            self.stepper_motion_stopped()

    def cb_stepper_new_state(self, state_new, state_previous):
        if self.stepper != None and state_new == BrickStepper.STATE_STOP:
            self.stepper_motion_stopped()

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
