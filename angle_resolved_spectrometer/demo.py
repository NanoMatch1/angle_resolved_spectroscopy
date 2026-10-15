'''Record a complete simulated measurement, headless.

This runs the same steps as an operator at the real instrument (home, then a
reference scan and a sample scan, with a dark at the start of each), but with
the simulated motor controller and spectrometer software. The result is a data
folder exactly like a real one, ready for ``run_analysis.py``.
'''

from .calibration import MELBOURNE_CALIBRATION
from .instrument import AngleResolvedSpectrometer
from .motion import SimulatedUno, UnoMotorController
from .scans import ScanSession, record_scan_plan, specular_plan
from .simulated_spectrometer import SimulatedSpectrometerSoftware


def simulated_instrument(log=print):
    controller = UnoMotorController(SimulatedUno(), pause_seconds=0, poll_interval_seconds=0, sleep=lambda seconds: None)
    return AngleResolvedSpectrometer(controller, MELBOURNE_CALIBRATION, log=log)


def record_simulated_measurement(data_folder, plans_by_role=None, instrument=None, log=print):
    '''Scan each role's plan, saving one spectrum per point. Returns the instrument used.

    plans_by_role: {"reference": plan, "sample": plan}; default is a specular
    20-60 deg scan in 10 deg steps for both.
    '''
    plans_by_role = plans_by_role or {role: specular_plan(20, 60, 10) for role in ('reference', 'sample')}
    instrument = instrument or simulated_instrument(log)
    software = SimulatedSpectrometerSoftware(data_folder)
    instrument.home()
    for role, plan in plans_by_role.items():
        record_scan_plan(data_folder, role, plan)
        software.save_dark(role)
        session = ScanSession(instrument, plan)
        session.start()
        while True:
            software.save_spectrum(role, *instrument.arm_angles)
            if not session.advance():
                break
    return instrument
