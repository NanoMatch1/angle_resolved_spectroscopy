'''Serial protocol, motor controller and simulated Uno.'''

import pytest

from angle_resolved_spectrometer.motion import SimulatedUno, UnoMotorController
from angle_resolved_spectrometer.motion import serial_protocol


def make_controller(polls_while_moving=1):
    uno = SimulatedUno(polls_while_moving=polls_while_moving)
    controller = UnoMotorController(uno, pause_seconds=0, poll_interval_seconds=0, sleep=lambda seconds: None)
    controller.read_waiting_lines()  # boot message
    return controller, uno


# --- protocol ---------------------------------------------------------------------

def test_command_strings():
    assert serial_protocol.move_command('X', -4141) == 'mox-4141'
    assert serial_protocol.move_command('Z', 600.0) == 'moz600'
    assert serial_protocol.set_position_command(532, 532, 0) == 'setpos532,532,0'


@pytest.mark.parametrize('reply_lines', [
    ['S0', '532,-20,7'],      # flag on its own line
    ['p:532,-20,7;'],         # two-character prefix and suffix, as the original parser assumed
])
def test_position_reply_formats(reply_lines):
    assert serial_protocol.parse_position_reply(reply_lines) == (532, -20, 7)


def test_position_reply_without_z_and_garbage():
    assert serial_protocol.parse_position_reply(['10,20']) == (10, 20, 0)
    with pytest.raises(ValueError):
        serial_protocol.parse_position_reply(['S0'])


# --- controller against the simulator ----------------------------------------------

def test_move_waits_through_running_polls():
    controller, uno = make_controller(polls_while_moving=3)
    controller.move_relative('Y', 250)
    assert uno.step_counters['Y'] == 250
    assert uno.received_commands.count('isrun') == 4  # three "running", then "stopped"


def test_stale_acknowledgement_is_not_mistaken_for_stopped():
    # The simulator acknowledges moves with S0; is_moving must ignore that and ask afresh.
    controller, uno = make_controller(polls_while_moving=1)
    controller.start_relative_move('X', 10)
    assert controller.is_moving() is True
    assert controller.is_moving() is False


def test_set_and_read_step_counters():
    controller, uno = make_controller()
    controller.set_step_counters(532, 600, -3)
    assert controller.read_step_counters() == (532, 600, -3)


def test_rejected_setpos_raises():
    controller, uno = make_controller()
    uno._respond_to = lambda command: uno._reply(serial_protocol.STATUS_INVALID_COMMAND)
    with pytest.raises(RuntimeError):
        controller.set_step_counters(1, 2, 3)


def test_home_reads_to_end_of_response_and_zeroes_arms():
    controller, uno = make_controller()
    controller.move_relative('X', 100)
    report = controller.drive_to_limit_switches()
    assert serial_protocol.END_OF_RESPONSE not in report
    assert uno.steps_from_limit_switch['X'] == 0


def test_unknown_command_gets_invalid_flag():
    controller, uno = make_controller()
    controller.send('wiggle')
    assert controller.wait_for_status_flag() == serial_protocol.STATUS_INVALID_COMMAND
