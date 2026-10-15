'''A stand-in for the Arduino Uno that speaks the same serial protocol.

It behaves like an open pyserial port: commands are written to it, and the
replies are read back line by line. Use it to run the GUI or the tests without
the instrument.

It also tracks each motor's distance from its limit switch, separately from
the step counters the controller reports, so tests can check where an arm
physically ended up.
'''

from . import serial_protocol

BOOT_MESSAGE = 'Angle-resolved spectrometer motor controller (simulated)'


class SimulatedUno:

    def __init__(self, polls_while_moving=1):
        '''polls_while_moving: how many ``isrun`` polls answer "running" after each move.'''
        self.polls_while_moving = polls_while_moving
        self.step_counters = {'X': 0, 'Y': 0, 'Z': 0}
        self.steps_from_limit_switch = {'X': 0, 'Y': 0, 'Z': 0}
        self.received_commands = []
        self._remaining_running_polls = 0
        self._output_lines = [BOOT_MESSAGE]

    # --- the pyserial methods the controller uses ------------------------------

    def write(self, data):
        for command in data.decode().splitlines():
            command = command.strip()
            if command:
                self.received_commands.append(command)
                self._respond_to(command)
        return len(data)

    @property
    def in_waiting(self):
        return sum(len(line) + 2 for line in self._output_lines)

    def readline(self):
        if not self._output_lines:
            return b''
        return (self._output_lines.pop(0) + '\r\n').encode()

    def reset_input_buffer(self):
        self._output_lines.clear()

    def close(self):
        pass

    # --- command handling -------------------------------------------------------

    def _reply(self, *lines):
        self._output_lines.extend(lines)

    def _respond_to(self, command):
        for axis, prefix in serial_protocol.MOVE_COMMAND_PREFIX.items():
            if command.startswith(prefix):
                return self._move(axis, command[len(prefix):])

        if command == serial_protocol.IS_RUNNING_COMMAND:
            if self._remaining_running_polls > 0:
                self._remaining_running_polls -= 1
                return self._reply(serial_protocol.STATUS_RUNNING)
            return self._reply(serial_protocol.STATUS_OK)

        if command == serial_protocol.HOME_COMMAND:
            for axis in ('X', 'Y'):
                self.steps_from_limit_switch[axis] = 0
                self.step_counters[axis] = 0
            return self._reply('Homing X', 'Homing Y', 'Homed', serial_protocol.END_OF_RESPONSE)

        if command == serial_protocol.REPORT_POSITION_COMMAND:
            counters = self.step_counters
            return self._reply(serial_protocol.STATUS_OK,
                               '{},{},{}'.format(counters['X'], counters['Y'], counters['Z']),
                               serial_protocol.END_OF_RESPONSE)

        if command.startswith(serial_protocol.SET_POSITION_COMMAND_PREFIX):
            return self._set_position(command[len(serial_protocol.SET_POSITION_COMMAND_PREFIX):])

        self._reply(serial_protocol.STATUS_INVALID_COMMAND)

    def _move(self, axis, steps_text):
        try:
            steps = int(steps_text)
        except ValueError:
            return self._reply(serial_protocol.STATUS_INVALID_COMMAND)
        self.step_counters[axis] += steps
        self.steps_from_limit_switch[axis] += steps
        self._remaining_running_polls = self.polls_while_moving
        self._reply(serial_protocol.STATUS_OK)

    def _set_position(self, arguments):
        try:
            x_steps, y_steps, z_steps = (int(value) for value in arguments.split(','))
        except ValueError:
            return self._reply(serial_protocol.STATUS_INVALID_COMMAND)
        self.step_counters.update({'X': x_steps, 'Y': y_steps, 'Z': z_steps})
        self._reply(serial_protocol.STATUS_OK)
