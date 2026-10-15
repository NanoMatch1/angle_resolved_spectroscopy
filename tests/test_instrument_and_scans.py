'''Angle control, scan plans, the scan list file and scan sessions.'''

import json

import numpy as np
import pytest

from angle_resolved_spectrometer import MELBOURNE_CALIBRATION
from angle_resolved_spectrometer.demo import simulated_instrument
from angle_resolved_spectrometer.instrument import AngleOutOfRangeError, PositionUnknownError
from angle_resolved_spectrometer import scans

SOURCE_ARM = MELBOURNE_CALIBRATION.source_arm


def homed_instrument():
    instrument = simulated_instrument(log=lambda message: None)
    instrument.home()
    return instrument, instrument.motor_controller.serial_connection


def physical_angle(uno, axis):
    '''The arm angle implied by the simulator's distance from the limit switch.'''
    arm = MELBOURNE_CALIBRATION.arm(axis)
    return arm.steps_to_angle(uno.steps_from_limit_switch[axis] - arm.limit_switch_to_vertical_steps)


# --- instrument ------------------------------------------------------------------

def test_refuses_to_move_before_position_is_known():
    instrument = simulated_instrument(log=lambda message: None)
    with pytest.raises(PositionUnknownError):
        instrument.go_to_angles(30, 30)


def test_home_parks_both_arms_at_park_angle():
    instrument, uno = homed_instrument()
    assert instrument.arm_angles == pytest.approx((10, 10), abs=0.05)
    assert physical_angle(uno, 'X') == pytest.approx(10, abs=0.05)
    assert physical_angle(uno, 'Y') == pytest.approx(10, abs=0.05)
    assert uno.step_counters['X'] == SOURCE_ARM.angle_to_steps(10)


def test_go_to_angles_moves_arms_to_the_right_place():
    instrument, uno = homed_instrument()
    instrument.go_to_angles(45, 30)
    instrument.go_to_angles('60', '60')  # strings from a GUI entry are fine
    assert physical_angle(uno, 'X') == pytest.approx(60, abs=0.05)
    assert physical_angle(uno, 'Y') == pytest.approx(60, abs=0.05)
    assert instrument.read_controller_angles() == pytest.approx((60, 60), abs=0.05)


@pytest.mark.parametrize('x_angle, y_angle', [(5, 30), (30, 95), (-20, -20)])
def test_out_of_range_angle_raises_without_moving(x_angle, y_angle):
    instrument, uno = homed_instrument()
    commands_before = list(uno.received_commands)
    with pytest.raises(AngleOutOfRangeError):
        instrument.go_to_angles(x_angle, y_angle)
    assert uno.received_commands == commands_before


def test_non_numeric_angle_raises_without_moving():
    instrument, uno = homed_instrument()
    commands_before = list(uno.received_commands)
    with pytest.raises(ValueError):
        instrument.go_to_angles('forty', 30)
    assert uno.received_commands == commands_before


def test_declare_current_angles_sets_counters():
    instrument = simulated_instrument(log=lambda message: None)
    instrument.declare_current_angles(25, 35)
    uno = instrument.motor_controller.serial_connection
    assert uno.step_counters['X'] == SOURCE_ARM.angle_to_steps(25)
    instrument.go_to_angles(30, 35)  # now allowed
    assert uno.step_counters['X'] == SOURCE_ARM.angle_to_steps(30)


def test_polariser_turns_by_approximate_steps():
    instrument, uno = homed_instrument()
    instrument.rotate_polariser(90)
    assert uno.step_counters['Z'] == 600


# --- plans -------------------------------------------------------------------------

def test_inclusive_range_has_no_float_drift():
    angles = scans.inclusive_angle_range(20, 21, 0.1)
    assert len(angles) == 11
    assert angles[3] == 20.3 and angles[-1] == 21.0


@pytest.mark.parametrize('arguments', [(20, 60, 0), (60, 20, 5)])
def test_bad_ranges_raise(arguments):
    with pytest.raises(ValueError):
        scans.inclusive_angle_range(*arguments)


def test_specular_and_uncoupled_plans():
    assert scans.specular_plan(20, 30, 5) == [(20, 20), (25, 25), (30, 30)]
    assert scans.uncoupled_plan('X', (20, 30, 10), (40, 50, 10)) == [(20, 40), (30, 40), (20, 50), (30, 50)]
    assert scans.uncoupled_plan('Y', (20, 30, 10), (40, 40, 1)) == [(40, 20), (40, 30)]


def test_scan_list_keeps_the_other_role(tmp_path):
    scans.record_scan_plan(tmp_path, 'reference', scans.specular_plan(20, 30, 10))
    scans.record_scan_plan(tmp_path, 'sample', [(20, 40), (30, 40)])
    stored = json.loads((tmp_path / scans.SCAN_LIST_FILENAME).read_text())
    assert stored == {'reference': [[20.0, 20.0], [30.0, 30.0]], 'sample': [[20.0, 40.0], [30.0, 40.0]]}
    assert scans.read_scan_list(tmp_path)['sample'] == [(20.0, 40.0), (30.0, 40.0)]
    with pytest.raises(ValueError):
        scans.record_scan_plan(tmp_path, 'mirror', [])


# --- sessions ------------------------------------------------------------------------

def test_session_visits_each_point_then_returns_to_start():
    instrument, uno = homed_instrument()
    session = scans.ScanSession(instrument, scans.specular_plan(20, 40, 10))
    visited = []
    session.start()
    visited.append(instrument.arm_angles)
    while session.advance():
        visited.append(instrument.arm_angles)
    np.testing.assert_allclose(visited, [(20, 20), (30, 30), (40, 40)], atol=0.05)
    assert session.is_finished and 'complete' in session.progress_text
    assert instrument.arm_angles == pytest.approx((20, 20), abs=0.05)
    assert session.advance() is False


def test_session_checks_every_point_before_moving():
    instrument, uno = homed_instrument()
    commands_before = list(uno.received_commands)
    session = scans.ScanSession(instrument, [(20, 20), (95, 95)])
    with pytest.raises(AngleOutOfRangeError):
        session.start()
    assert uno.received_commands == commands_before
