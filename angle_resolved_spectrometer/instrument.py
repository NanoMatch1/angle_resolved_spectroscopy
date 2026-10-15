'''The instrument in angles: source arm (X), detector arm (Y), polariser (Z).

:class:`AngleResolvedSpectrometer` turns angle requests into step moves,
enforces the angle limits, and refuses to move until it knows where the arms
are (after homing, or after the operator declares their angles).
'''

from .calibration import MELBOURNE_CALIBRATION

ARM_AXES = ('X', 'Y')


class AngleOutOfRangeError(ValueError):
    pass


class PositionUnknownError(RuntimeError):
    pass


class AngleResolvedSpectrometer:

    def __init__(self, motor_controller, calibration=MELBOURNE_CALIBRATION, log=print):
        '''
        motor_controller: a :class:`~angle_resolved_spectrometer.motion.UnoMotorController`.
        calibration: an :class:`~angle_resolved_spectrometer.calibration.InstrumentCalibration`.
        log: where status messages go (``print`` by default; the GUI passes its own).
        '''
        self.motor_controller = motor_controller
        self.calibration = calibration
        self.log = log
        self.arm_steps = {'X': 0, 'Y': 0}
        self.polariser_steps = 0
        self.position_known = False

    # --- conversions ------------------------------------------------------------

    def angle_to_steps(self, axis, angle_deg):
        return self.calibration.arm(axis).angle_to_steps(angle_deg)

    def steps_to_angle(self, axis, steps):
        return self.calibration.arm(axis).steps_to_angle(steps)

    @property
    def arm_angles(self):
        '''The (X, Y) angles in degrees, as tracked by this program.'''
        return tuple(self.steps_to_angle(axis, self.arm_steps[axis]) for axis in ARM_AXES)

    def check_angles(self, x_angle_deg, y_angle_deg):
        '''Raise AngleOutOfRangeError unless both angles are inside the arm limits.'''
        for axis, angle in zip(ARM_AXES, (x_angle_deg, y_angle_deg)):
            arm = self.calibration.arm(axis)
            if not arm.allows(angle):
                raise AngleOutOfRangeError('{} angle {} deg is outside {}-{} deg.'.format(
                    axis, angle, arm.minimum_angle_deg, arm.maximum_angle_deg))

    # --- motion -----------------------------------------------------------------

    def home(self):
        '''Find the limit switches, then park both arms at the park angle.'''
        self.log('Homing: driving arms to their limit switches...')
        self.motor_controller.drive_to_limit_switches()
        park_angle = self.calibration.park_angle_deg
        park_steps = {axis: self.angle_to_steps(axis, park_angle) for axis in ARM_AXES}
        for axis in ARM_AXES:
            switch_to_park = self.calibration.arm(axis).limit_switch_to_vertical_steps + park_steps[axis]
            self.motor_controller.start_relative_move(axis, switch_to_park)
        self.motor_controller.wait_until_stopped()
        self.motor_controller.set_step_counters(park_steps['X'], park_steps['Y'], self.polariser_steps)
        self.arm_steps = park_steps
        self.position_known = True
        self.log('Homed. Arms parked at {} deg.'.format(park_angle))

    def go_to_angles(self, x_angle_deg, y_angle_deg):
        '''Move the source arm to x and the detector arm to y (degrees from vertical).'''
        x_angle_deg, y_angle_deg = float(x_angle_deg), float(y_angle_deg)
        if not self.position_known:
            raise PositionUnknownError('Arm positions are unknown: home the instrument '
                                       '(or set the motor positions) before moving.')
        self.check_angles(x_angle_deg, y_angle_deg)
        targets = {'X': self.angle_to_steps('X', x_angle_deg), 'Y': self.angle_to_steps('Y', y_angle_deg)}
        for axis in ARM_AXES:
            steps_to_move = targets[axis] - self.arm_steps[axis]
            if steps_to_move != 0:
                self.motor_controller.start_relative_move(axis, steps_to_move)
        self.motor_controller.wait_until_stopped()
        self.arm_steps = targets
        self.log('Arms at X {:g} deg, Y {:g} deg.'.format(x_angle_deg, y_angle_deg))

    def declare_current_angles(self, x_angle_deg, y_angle_deg):
        '''Tell the instrument where the arms are now (e.g. after setting them by hand).'''
        x_angle_deg, y_angle_deg = float(x_angle_deg), float(y_angle_deg)
        steps = {'X': self.angle_to_steps('X', x_angle_deg), 'Y': self.angle_to_steps('Y', y_angle_deg)}
        self.motor_controller.set_step_counters(steps['X'], steps['Y'], self.polariser_steps)
        self.arm_steps = steps
        self.position_known = True
        self.log('Positions set: X {:g} deg, Y {:g} deg.'.format(x_angle_deg, y_angle_deg))

    def read_controller_angles(self):
        '''Ask the controller for its step counters and return the (X, Y) angles.'''
        x_steps, y_steps, z_steps = self.motor_controller.read_step_counters()
        self.arm_steps = {'X': x_steps, 'Y': y_steps}
        self.polariser_steps = z_steps
        angles = self.arm_angles
        self.log('Controller reports X {:.2f} deg, Y {:.2f} deg.'.format(*angles))
        return angles

    def rotate_polariser(self, degrees):
        '''Turn the polariser by a relative angle. The Z calibration is approximate.'''
        steps = round(degrees * self.calibration.polariser_steps_per_degree)
        self.motor_controller.move_relative('Z', steps)
        self.polariser_steps += steps
        self.log('Polariser turned {:g} deg ({} steps).'.format(degrees, steps))
