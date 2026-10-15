'''Step-level control of the three stepper motors through the Arduino Uno.

This layer knows the serial protocol and nothing about angles. It takes any
object with the pyserial methods it uses (``write``, ``readline``,
``in_waiting``, ``reset_input_buffer``), so the same code drives the real Uno
or :class:`~angle_resolved_spectrometer.motion.simulated_uno.SimulatedUno`.
'''

import time

from . import serial_protocol

# The Uno resets when the port opens and needs about two seconds to boot.
UNO_BOOT_SECONDS = 2.0


class UnoMotorController:

    def __init__(self, serial_connection, pause_seconds=0.1, poll_interval_seconds=0.2, sleep=time.sleep):
        '''
        serial_connection: an open pyserial ``Serial`` (or a stand-in with the same methods).
        pause_seconds: wait after each command, giving the Uno time to act on it.
        poll_interval_seconds: wait between ``isrun`` polls while motors move.
        sleep: the function used to wait; tests pass a no-op.
        '''
        self.serial_connection = serial_connection
        self.pause_seconds = pause_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.sleep = sleep

    @classmethod
    def open_port(cls, port_name, **controller_options):
        '''Open a real serial port (e.g. ``"COM7"`` or ``"/dev/ttyACM0"``) and wait for the Uno to boot.'''
        import serial  # imported here so simulation and analysis do not need pyserial

        connection = serial.Serial(port_name, serial_protocol.BAUD_RATE)
        controller = cls(connection, **controller_options)
        controller.sleep(UNO_BOOT_SECONDS)
        controller.read_waiting_lines()  # discard the boot message
        return controller

    # --- low-level line I/O -------------------------------------------------

    def send(self, command):
        '''Send one command line.'''
        self.serial_connection.write('{}\n'.format(command).encode())
        self.sleep(self.pause_seconds)

    def read_waiting_lines(self):
        '''All complete lines currently waiting, stripped of line endings.'''
        lines = []
        while self.serial_connection.in_waiting > 0:
            line = self.serial_connection.readline().decode(errors='replace').strip()
            if line:
                lines.append(line)
        return lines

    def read_until_end_of_response(self):
        '''Read lines until ``#CF`` arrives; returns the lines before it.'''
        reply_lines = []
        while True:
            for line in self.read_waiting_lines():
                if line == serial_protocol.END_OF_RESPONSE:
                    return reply_lines
                reply_lines.append(line)
            self.sleep(0.01)

    def wait_for_status_flag(self):
        '''Block until a status flag arrives and return the most recent one.'''
        while True:
            flags = [line for line in self.read_waiting_lines()
                     if line in serial_protocol.STATUS_FLAG_MEANINGS]
            if flags:
                return flags[-1]
            self.sleep(self.pause_seconds)

    # --- motor commands -----------------------------------------------------

    def start_relative_move(self, axis, steps):
        '''Start moving one axis ('X', 'Y' or 'Z') without waiting for it to finish.'''
        self.send(serial_protocol.move_command(axis, steps))

    def is_moving(self):
        # Clear stale flags first (e.g. an acknowledgement of the move command),
        # so the flag we read is the answer to this question.
        self.serial_connection.reset_input_buffer()
        self.send(serial_protocol.IS_RUNNING_COMMAND)
        return self.wait_for_status_flag() == serial_protocol.STATUS_RUNNING

    def wait_until_stopped(self):
        while self.is_moving():
            self.sleep(self.poll_interval_seconds)

    def move_relative(self, axis, steps):
        '''Move one axis by a number of steps and wait until it stops.'''
        self.start_relative_move(axis, steps)
        self.wait_until_stopped()

    def drive_to_limit_switches(self):
        '''Run X and Y onto their limit switches. Returns the controller's report lines.'''
        self.send(serial_protocol.HOME_COMMAND)
        return self.read_until_end_of_response()

    def set_step_counters(self, x_steps, y_steps, z_steps):
        '''Tell the controller where the motors are, without moving them.'''
        self.send(serial_protocol.set_position_command(x_steps, y_steps, z_steps))
        flag = self.wait_for_status_flag()
        if flag != serial_protocol.STATUS_OK:
            raise RuntimeError('Controller rejected setpos: {}'.format(flag))

    def read_step_counters(self):
        '''The controller's (x, y, z) step counters.'''
        self.serial_connection.reset_input_buffer()
        self.send(serial_protocol.REPORT_POSITION_COMMAND)
        return serial_protocol.parse_position_reply(self.read_until_end_of_response())
