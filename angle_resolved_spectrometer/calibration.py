'''Angle calibration of the two arms.

Angles are measured from vertical: 0 deg points straight down at the sample
(normal incidence), and 90 deg is horizontal (grazing). Each arm has its own
angle. In specular geometry both arms sit at the same angle, so the full angle
between source and detector is twice that.
'''

from dataclasses import dataclass


@dataclass(frozen=True)
class ArmCalibration:
    steps_per_degree: float
    # Steps from the limit switch to vertical (0 deg); negative means "away from the switch".
    limit_switch_to_vertical_steps: int
    # Allowed angle range. The lower bound keeps the arms from colliding near vertical.
    minimum_angle_deg: float
    maximum_angle_deg: float

    def angle_to_steps(self, angle_deg):
        return int(angle_deg * self.steps_per_degree)

    def steps_to_angle(self, steps):
        return steps / self.steps_per_degree

    def allows(self, angle_deg):
        return self.minimum_angle_deg <= angle_deg <= self.maximum_angle_deg


@dataclass(frozen=True)
class InstrumentCalibration:
    source_arm: ArmCalibration      # motor X
    detector_arm: ArmCalibration    # motor Y
    polariser_steps_per_degree: float  # motor Z (approximate)
    # Where the arms park after homing; also the safe starting angle.
    park_angle_deg: float

    def arm(self, axis):
        return {'X': self.source_arm, 'Y': self.detector_arm}[axis]


# The values the Melbourne instrument ran with (2024-2025).
MELBOURNE_CALIBRATION = InstrumentCalibration(
    source_arm=ArmCalibration(steps_per_degree=9584 / 180, limit_switch_to_vertical_steps=-4673,
                              minimum_angle_deg=10, maximum_angle_deg=90),
    detector_arm=ArmCalibration(steps_per_degree=9584 / 180, limit_switch_to_vertical_steps=-5006,
                                minimum_angle_deg=10, maximum_angle_deg=90),
    polariser_steps_per_degree=600 / 90,
    park_angle_deg=10,
)
