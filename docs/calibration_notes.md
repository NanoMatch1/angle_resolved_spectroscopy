# Calibration notes

The values in [`calibration.py`](../angle_resolved_spectrometer/calibration.py) are the ones the instrument ran with in 2024–2025. This page records where they came from and the open questions about them.

## Arms (motors X and Y)

| Quantity | X (source) | Y (detector) |
|---|---|---|
| Steps per degree | 9584 / 180 ≈ 53.2 | 9584 / 180 ≈ 53.2 |
| Limit switch → vertical (0°) | −4673 steps | −5006 steps |
| Allowed range | 10°–90° | 10°–90° |
| Park angle after homing | 10° | 10° |

Homing drives each arm onto its limit switch. The arm then moves `limit_switch_to_vertical_steps + park_steps` to reach the park angle, and the controller's step counter is set to the park angle's step count.

### Open questions

- **Steps per degree versus the early calibration.** The first control script opened with these notes:

  ```
  initial cal: X 10 deg, 9770 steps from vertical
  initial cal: X 170 deg, -9680 steps from vertical
  initial cal: Y 170 deg, 9680 steps from vertical
  ```

  That is about 9680 steps per 80°, or roughly 121 steps per degree. The value used in practice was 53.2 steps per degree. The early notes may come from a different microstepping setting or angle convention.
  <!-- TODO(sam): confirm which is right (measure one arm's 0-90 deg travel with a protractor or a level). -->
- **Upper limit versus limit-switch position.** With 53.2 steps per degree, the X switch is 4673 steps ≈ 87.8° from vertical and the Y switch is 5006 steps ≈ 94.0°. So an X request near 90° asks for a point past the X switch. In practice scans ran between about 15° and 75°.
  <!-- TODO(sam): lower maximum_angle_deg to below the switch angle once checked. -->

## Polariser (motor Z)

About 600 steps per 90°, from a note in the original script. There is no home switch, so polariser moves are relative to wherever it was at power-up.
