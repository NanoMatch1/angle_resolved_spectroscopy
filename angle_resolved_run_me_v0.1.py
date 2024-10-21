import os
import serial
import struct
import time
import numpy as np
import tkinter as tk
from tkinter import ttk
from ars_gui import SpectrometerGUI

# // initial cal: X motor 0 angle: -10720 steps from limit switch
# // initial cal: X 10 deg, 9770 steps from vertical
# // initial cal: X 170 deg, -9680 steps from vertical

# // Initial cal: Y motor 0 angle: -10252 steps from limit switch
# // initial cal: Y 170 deg, 9680 steps from vertical
# // initial cal: Y 10 deg, -9680 steps from vertical
# (9680*2)/160

class AngleResolvedSpectrometer:

    def __init__(self, serial_port='COM4', working_dir=None):
        self.uno_serial = serial.Serial(serial_port, 9600)
        time.sleep(2)
        print(self.read_command_from_uno())

        if working_dir is None:
            working_dir = os.path.dirname(os.path.abspath(__file__))
        self.working_dir = working_dir

        # Calibration data (based on your provided calibration info)
        self.steps_per_degree = {
            'X': (9680*2)/160,  # Steps per degree for X axis
            'Y': (9680*2)/160,  # Steps per degree for Y axis
        }

        # Store current positions in steps (start at home position, 0 degrees)
        self.current_position = {'X': 0, 'Y': 0}  # Steps
        self.current_angle = {'X': 0, 'Y': 0}  # Degrees

        self.x_home = -10720
        self.y_home = -10252

        self.soft_limit = 10 # degrees

        self.hard_limits = {
            # 'X': ((self.angle_to_steps("X", 15)), 10720),
            'X': (self.angle_to_steps("X", self.soft_limit), self.angle_to_steps("X", 90)),
            'Y': (self.angle_to_steps("Y", self.soft_limit), self.angle_to_steps("Y", 90)),
        }

        self.measure_mode = 'specular'
        self.measure_mode = 'variable'
        
        self.commandDict = {
            'wait': self.wait_for_motors,
            'home': self.home_motors,
            'a': self.go_to_angle,
            'wai': self.get_current_position,
            'basic': self.basic_scan,
            'debug': self.debug,
            # 'pos': self.get_motor_positions,
            'mox': self.move_x,
            'moy': self.move_y,
            'setpos': self.set_motor_positions,
            'a' : self.go_to_angle,
            'z' : self.move_z,
        }

        self.flag_dict = {'S0': 'ok',
                          'R1': 'motors running',
                          'F0': 'invalid command',
                          '#CF': 'end of response'
        }

    # def __initialise(self):
        # print("Welcome to ")
    
    def debug(self):
        print("Debugging...")
        breakpoint()

    def move_x(self, steps):
        self.send_command_to_UNO('mox{}'.format(steps))
        time.sleep(0.1)
        self.wait_for_motors()

    def move_y(self, steps):
        self.send_command_to_UNO('moy{}'.format(steps))
        time.sleep(0.1)
        self.wait_for_motors()

    def move_z(self, steps):
        self.send_command_to_UNO('moz{}'.format(steps))
        time.sleep(0.1)
        self.wait_for_motors()

    def process_coms(self, command):
        cmd = command.split(' ')

        if len(cmd) > 1:
            command = cmd[0]
            args = cmd[1:]
            if command in self.commandDict:
                return self.commandDict[command](*args)
            else:
                print('Invalid command')
                return

        else:
            if command in self.commandDict:
                return self.commandDict[command]()
            else:
                print('Invalid command')
                return 
            
    # def get_motor_positions(self):
    #     """Get current motor positions."""
    #     print("Getting current motor positions...")
    #     self.send_command_to_UNO('pos')
    #     time.sleep(0.1)
    #     response = self.read_from_serial_until()
    #     pos = response[0][2:-2].split(',')
    #     current_steps = (int(pos[0]), int(pos[1]))
    #     print("Finished getting motor positions.")
    #     return current_steps


    def home_motors(self, soft_limit=None):
        if soft_limit is None:
            soft_limit = self.soft_limit
            
        # print("Homing motors...")

        self.send_command_to_UNO('home')
        time.sleep(0.1)
        responses = self.read_from_serial_until()
        # print(responses)

        # calculate steps from zero to soft limit
        steps_soft_limit_x = self.angle_to_steps('X', soft_limit)
        steps_soft_limit_y = self.angle_to_steps('Y', soft_limit)

        # calculate steps from limit switch to soft limit 
        steps_to_soft_home_x = self.x_home+steps_soft_limit_x
        steps_to_soft_home_y = self.y_home+steps_soft_limit_y

        # self.wait_for_motors()

        # move from limit switch (hard limit) to soft limit 
        self.send_command_to_UNO('mox{}'.format(steps_to_soft_home_x))
        self.send_command_to_UNO('moy{}'.format(steps_to_soft_home_y))

        self.wait_for_motors()

        # set motor positions in controller to soft limit (in steps)
        self.set_motor_positions(steps_soft_limit_x, steps_soft_limit_y, 0)

        # set current position and angle to soft limit - necessary for correctly calculating relative movements
        self.current_position = {'X': steps_soft_limit_x, 'Y': steps_soft_limit_y}
        self.current_angle = {'X': soft_limit, 'Y': soft_limit}

        print("Motors homed to {} degrees.".format(soft_limit))

    def set_motor_positions(self, x_pos, y_pos, z_pos):
        self.send_command_to_UNO('setpos{},{},{}'.format(x_pos, y_pos, z_pos))
        flag = self.wait_for_flag()
        if flag == 'S0':
            print("Motor positions set successfully.")


    def angle_to_steps(self, axis, angle):
        """Convert angle to steps for the given axis."""
        steps = int(angle * self.steps_per_degree[axis])
        return steps

    def steps_to_angle(self, axis, steps):
        """Convert steps to angle for the given axis."""
        angle = steps / self.steps_per_degree[axis]
        return angle

    def go_to_angle(self, x_angle, y_angle):
        """Move both motors to the given angle (specular reflectance mode)."""
        try:
            x_angle = float(x_angle)
            y_angle = float(y_angle)
        except ValueError:
            print("Error: Invalid angle value.")

        # Convert angle to steps for both motors
        x_target = self.angle_to_steps('X', x_angle)
        y_target = self.angle_to_steps('Y', y_angle)

        if x_target > self.hard_limits['X'][1] or x_target < self.hard_limits['X'][0]:
            print("Error: X angle exceeds hard limits.")
            return
        if y_target > self.hard_limits['Y'][1] or y_target < self.hard_limits['Y'][0]:
            print("Error: Y angle exceeds hard limits.")
            return
        
        # Calculate relative movement from current position
        x_move_steps = x_target - self.current_position['X']
        y_move_steps = y_target - self.current_position['Y']

        # Send commands to motors
        print("sending command")
        if x_move_steps != 0:
            self.send_command_to_UNO('mox{}'.format(x_move_steps))
        if y_move_steps != 0:
            self.send_command_to_UNO('moy{}'.format(y_move_steps))

        # Wait for motors to finish moving
        self.wait_for_motors()

        # Update current positions and angles
        self.current_position['X'] = x_target
        self.current_position['Y'] = y_target
        self.current_angle['X'] = x_angle
        self.current_angle['Y'] = y_angle

        # print(f"Motors moved to {angle} degrees (specular).")
        print(f"Motors moved to X: {x_angle} degrees, Y: {y_angle} degrees.")

    def wait_for_motors(self, delay=0.2):
        """Wait until the motors are done moving."""
        while True:
            self.send_command_to_UNO('isrun')
            time.sleep(delay)
            response = self.wait_for_flag()
            if response == "S0":
                break
            time.sleep(delay)

    def send_command_to_UNO(self, command):
        """Send a command to the Arduino."""
        self.uno_serial.write('{}\n'.format(command).encode())
        time.sleep(0.1)

    def read_command_from_uno(self):
        """Read response from Arduino."""
        response = ''
        while self.uno_serial.in_waiting > 0:
            response += self.uno_serial.readline().decode()
            # print(response)
        
        return response.strip()
    
    def wait_for_flag(self):
        """Wait for a specific flag to be received."""
        while True:
            response = self.read_command_from_uno()
            response = response.splitlines()
            for res in response:
                if res in self.flag_dict.keys():
                    return res
            time.sleep(0.1)

    def read_from_serial_until(self, end_flag='#CF', report=False):
        """Read from serial until end flag is encountered."""
        responses = []
        while True:
            # print("Reading from serial...")
            response = self.read_command_from_uno()
            if response == '':
                time.sleep(0.01)
                continue
            if end_flag in response:
                # print("End flag found.")
                print(response)
                response = response[:-len('\r\n'+end_flag)]
                responses.append(response)
                return responses
            
            responses.append(response)
            print(response)

    def calibration(self):
        pass

    def send_and_receive(self, command):
        '''Blocking. waits until axes are done'''
        """Send a command to Arduino and get the response."""
        self.send_command_to_UNO(command)
        return self.read_from_serial_until()

    def get_current_position(self):
        """Retrieve current position of motors."""
        self.send_command_to_UNO('pos')
        time.sleep(0.1)
        response = self.read_from_serial_until()
        pos = response[0][2:-2].split(',')
        current_steps = (int(pos[0]), int(pos[1]))
        self.current_position = {'X': int(pos[0]), 'Y': int(pos[1])}
        self.current_angle = {'X': self.steps_to_angle('X', self.current_position['X']),
                              'Y': self.steps_to_angle('Y', self.current_position['Y'])}
        
        print(f'X: {self.current_angle["X"]}, Y: {self.current_angle["Y"]}')
        
    # def run_scan(self, start_angle, end_angle, resolution):
    #     series_name = input("Enter series name: ")
    #     self.scan_log = []
    #     """Run a scan from start to end angle with given step size."""
    #     if abs(self.angle_to_steps('X', start_angle)) > self.hard_limits['X']:
    #         print("Start angle exceeds hard limit for X motor.")
    #         return
    #     if abs(self.angle_to_steps('Y', start_angle)) > self.hard_limits['Y']:
    #         print("Start angle exceeds hard limit for Y motor.")
    #         return
        
    #     angles = np.arange(start_angle, end_angle + resolution, resolution)
    #     print("Scan to commence at angles: ", angles)
    #     input("Press Enter to start the scan...")
    #     os.makedirs(os.path.join(self.working_dir, series_name), exist_ok=True)

    #     for angle in angles:
    #         self.go_to_angle(angle)
    #         self.scan_log.append([self.current_angle['X'], self.current_angle['Y']])
    #         input("Collect data at this angle and press Enter to continue...")
    #         # Do something with the spectrometer here
    #         # For example, take a measurement at the current angle
    #         # and store the data for further

    def rename_files(self, series_name, angles):
        """Rename files in the current directory with a given prefix and suffix."""
        # This is just a placeholder function for demonstration
        # takes the files that have been generated by the spectrometer and renames then with the correct angles
        pass

    def basic_scan(self, start_angle, end_angle, resolution):
        """Run a basic scan from start to end angle with given step size."""
        start_angle = float(start_angle)
        end_angle = float(end_angle)
        resolution = float(resolution)
        angles = np.arange(start_angle, end_angle + resolution, resolution)
        print("Scan to commence at angles: ", angles)
        input("Press Enter to start the scan...")

        for angle in angles:
            self.go_to_angle(angle)
            input("Collect data at this angle and press Enter to continue...")
            # Do something with the spectrometer here
            # For example, take a measurement at the current angle
            # and store the data for further

    def main_loop(self):
        """Main loop to receive commands."""
        while True:
            try:
                cmd = input("Enter command: ").strip().lower()

            # if cmd.startswith('a'):
            #     angle = cmd.split(' ')[1]
            #     self.go_to_angle(angle)

            # elif cmd == 'pos':
            #     self.get_current_position()
            #     print(f"Current positions: X: {self.current_angle['X']} degrees, Y: {self.current_angle['Y']} degrees")
            # elif cmd == 'home':
            #     self.home_motors()
            # elif cmd == 'exit':
            #     break
            # elif cmd in self.commandDict:
            #     self.process_coms(cmd)
                if cmd.startswith('z'):
                    angle = cmd.split(' ')[1]
                    self.send_command_to_UNO('moz{}'.format(angle))
                else:
                    self.process_coms(cmd)
                    # print("Invalid command")
            except Exception as e:
                print("Error:", e)
                continue

# Instantiate the spectrometer
ars = AngleResolvedSpectrometer()
app = SpectrometerGUI(ars)
app.mainloop()



# ars.main_loop()

# range is 15 deg (0/1) - 75 (1-13)
# z ~600 steps/90 deg


# TODO: change the final homing step to return to 15 degrees
# balance armature masses to reduce the load on the motors
# decrease motor current
