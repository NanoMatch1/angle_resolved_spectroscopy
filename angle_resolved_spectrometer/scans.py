'''Scan plans, the scan list file, and step-by-step scan sessions.

A *scan plan* is an ordered list of (X, Y) angle pairs. Acquisition is manual:
at each pair the operator records a spectrum in the spectrometer software, then
asks the session to move on. The spectrometer software numbers its files in
the order they are saved, so the plan order is what later ties each file to its
angles (see :mod:`angle_resolved_spectrometer.analysis.file_organisation`).

The scan list file, ``scan_list.json`` in the data folder, records the plan of
the reference run and of the sample run::

    {"reference": [[20.0, 20.0], [25.0, 25.0]], "sample": [[20.0, 20.0], [25.0, 25.0]]}
'''

import json
import os

SCAN_LIST_FILENAME = 'scan_list.json'
SCAN_ROLES = ('reference', 'sample')
_ANGLE_DECIMALS = 6


def inclusive_angle_range(start_deg, stop_deg, step_deg):
    '''Angles from start to stop inclusive, free of floating-point drift.'''
    if step_deg <= 0:
        raise ValueError('Step must be positive, got {}.'.format(step_deg))
    if stop_deg < start_deg:
        raise ValueError('Stop angle {} is below start angle {}.'.format(stop_deg, start_deg))
    number_of_points = int(round((stop_deg - start_deg) / step_deg)) + 1
    return [round(start_deg + index * step_deg, _ANGLE_DECIMALS) for index in range(number_of_points)]


def specular_plan(start_deg, stop_deg, step_deg):
    '''Both arms move together: angle of incidence equals angle of detection.'''
    return [(angle, angle) for angle in inclusive_angle_range(start_deg, stop_deg, step_deg)]


def uncoupled_plan(primary_axis, primary_range, secondary_range):
    '''Sweep the primary axis at each secondary-axis angle.

    primary_axis: 'X' or 'Y'. The other axis is the secondary axis.
    primary_range, secondary_range: (start, stop, step) in degrees.
    Returns (X, Y) pairs, with the primary axis changing fastest.
    '''
    if primary_axis not in ('X', 'Y'):
        raise ValueError("primary_axis must be 'X' or 'Y', got {!r}.".format(primary_axis))
    plan = []
    for secondary_angle in inclusive_angle_range(*secondary_range):
        for primary_angle in inclusive_angle_range(*primary_range):
            if primary_axis == 'X':
                plan.append((primary_angle, secondary_angle))
            else:
                plan.append((secondary_angle, primary_angle))
    return plan


# --- scan list file ---------------------------------------------------------------

def read_scan_list(data_folder):
    '''The {role: [(x, y), ...]} scan list in a data folder. Raises FileNotFoundError if absent.'''
    with open(os.path.join(data_folder, SCAN_LIST_FILENAME)) as scan_list_file:
        stored = json.load(scan_list_file)
    return {role: [tuple(pair) for pair in pairs] for role, pairs in stored.items()}


def record_scan_plan(data_folder, role, plan):
    '''Store the plan for one role ('reference' or 'sample'), keeping the other role's plan.'''
    if role not in SCAN_ROLES:
        raise ValueError('role must be one of {}, got {!r}.'.format(SCAN_ROLES, role))
    try:
        scan_list = read_scan_list(data_folder)
    except FileNotFoundError:
        scan_list = {}
    scan_list[role] = [[float(x_angle), float(y_angle)] for x_angle, y_angle in plan]
    path = os.path.join(data_folder, SCAN_LIST_FILENAME)
    with open(path, 'w') as scan_list_file:
        json.dump({key: [list(pair) for pair in value] for key, value in scan_list.items()}, scan_list_file)
    return path


def record_specular_scan_list(data_folder, start_deg, stop_deg, step_deg):
    '''Write a scan list for a specular reference run and sample run over the same angles.

    For data taken without the GUI's scan list (the analysis offers this when
    ``scan_list.json`` is missing).
    '''
    plan = specular_plan(start_deg, stop_deg, step_deg)
    for role in SCAN_ROLES:
        record_scan_plan(data_folder, role, plan)
    return plan


# --- scan session -------------------------------------------------------------------

class ScanSession:
    '''Walks the instrument through a plan, one point per call to :meth:`advance`.

    The session never blocks waiting for the operator, so a GUI can show a
    "Next" button and a script can loop. When the last point is done, the arms
    return to the first point.
    '''

    def __init__(self, instrument, plan):
        if not plan:
            raise ValueError('A scan plan needs at least one point.')
        self.instrument = instrument
        self.plan = list(plan)
        self.current_index = None
        self.is_finished = False

    @property
    def current_angles(self):
        return None if self.current_index is None else self.plan[self.current_index]

    @property
    def progress_text(self):
        if self.is_finished:
            return 'Scan complete ({} points).'.format(len(self.plan))
        if self.current_index is None:
            return 'Scan not started ({} points).'.format(len(self.plan))
        x_angle, y_angle = self.current_angles
        return 'Point {} of {}: X {:g} deg, Y {:g} deg. Record a spectrum, then continue.'.format(
            self.current_index + 1, len(self.plan), x_angle, y_angle)

    def start(self):
        '''Check every point is reachable, then move to the first one.'''
        for x_angle, y_angle in self.plan:
            self.instrument.check_angles(x_angle, y_angle)
        self.current_index = 0
        self.instrument.go_to_angles(*self.plan[0])

    def advance(self):
        '''Move to the next point. Returns False once the scan is finished.'''
        if self.current_index is None:
            raise RuntimeError('Call start() before advance().')
        if self.is_finished:
            return False
        if self.current_index + 1 < len(self.plan):
            self.current_index += 1
            self.instrument.go_to_angles(*self.plan[self.current_index])
            return True
        self.is_finished = True
        self.instrument.go_to_angles(*self.plan[0])
        return False
