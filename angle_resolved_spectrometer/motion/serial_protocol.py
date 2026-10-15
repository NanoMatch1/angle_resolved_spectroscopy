'''The text protocol spoken by the Arduino Uno motor controller.

Every command is one ASCII line ending in a newline, sent at 9600 baud. The Uno
answers with short status flags, and multi-line replies end with ``#CF``.

=================  ==========================================================
Command            Meaning
=================  ==========================================================
``mox<steps>``     Move the X (source) motor by a relative number of steps.
``moy<steps>``     Move the Y (detector) motor by a relative number of steps.
``moz<steps>``     Move the Z (polariser) motor by a relative number of steps.
``isrun``          Ask whether any motor is moving: ``R1`` yes, ``S0`` no.
``home``           Drive X and Y onto their limit switches; reply ends ``#CF``.
``pos``            Report the step counters as ``x,y,z``; reply ends ``#CF``.
``setpos<x>,<y>,<z>``  Overwrite the step counters without moving.
=================  ==========================================================

The firmware sketch is not yet published with this repository, so the shape of
the ``pos`` reply is inferred from how the original control script parsed it.
'''

import re

BAUD_RATE = 9600
END_OF_RESPONSE = '#CF'

STATUS_OK = 'S0'
STATUS_RUNNING = 'R1'
STATUS_INVALID_COMMAND = 'F0'

STATUS_FLAG_MEANINGS = {
    STATUS_OK: 'ok / motors stopped',
    STATUS_RUNNING: 'motors running',
    STATUS_INVALID_COMMAND: 'invalid command',
    END_OF_RESPONSE: 'end of response',
}

MOVE_COMMAND_PREFIX = {'X': 'mox', 'Y': 'moy', 'Z': 'moz'}
IS_RUNNING_COMMAND = 'isrun'
HOME_COMMAND = 'home'
REPORT_POSITION_COMMAND = 'pos'
SET_POSITION_COMMAND_PREFIX = 'setpos'

_INTEGER_PATTERN = re.compile(r'-?\d+')


def move_command(axis, steps):
    '''The command that moves one axis by a relative number of steps.'''
    return '{}{}'.format(MOVE_COMMAND_PREFIX[axis], int(steps))


def set_position_command(x_steps, y_steps, z_steps):
    '''The command that overwrites the controller's step counters.'''
    return '{}{},{},{}'.format(SET_POSITION_COMMAND_PREFIX, int(x_steps), int(y_steps), int(z_steps))


def parse_position_reply(reply_lines):
    '''The (x, y, z) step counters from the lines of a ``pos`` reply.

    Takes the last line that contains a comma, so status flags on their own
    lines are ignored. Raises ValueError if no position line is present.
    '''
    position_lines = [line for line in reply_lines if ',' in line]
    if not position_lines:
        raise ValueError('No position in controller reply: {!r}'.format(reply_lines))
    numbers = [int(field) for field in _INTEGER_PATTERN.findall(position_lines[-1])]
    if len(numbers) < 2:
        raise ValueError('Could not read X and Y steps from {!r}'.format(position_lines[-1]))
    numbers += [0] * (3 - len(numbers))
    return tuple(numbers[:3])
