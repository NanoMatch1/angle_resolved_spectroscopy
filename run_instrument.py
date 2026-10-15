'''Open the control window.

    python run_instrument.py --port COM7          the real instrument
    python run_instrument.py --simulate          no hardware: simulated motors and spectrometer

In simulation, a spectrum (and, at the first point, a dark) is "saved" into the
data folder automatically at each scan point, as the operator would do by hand.
'''

import argparse

from angle_resolved_spectrometer import MELBOURNE_CALIBRATION, AngleResolvedSpectrometer
from angle_resolved_spectrometer.motion import SimulatedUno, UnoMotorController


def simulated_acquisition(window):
    '''A callback that saves simulated spectra into whatever folder the window has selected.'''
    from angle_resolved_spectrometer.simulated_spectrometer import SimulatedSpectrometerSoftware

    software_by_folder = {}

    def save_spectrum(role, x_angle_deg, y_angle_deg):
        folder = window.data_folder.get()
        if folder not in software_by_folder:
            software_by_folder[folder] = SimulatedSpectrometerSoftware(folder)
        software = software_by_folder[folder]
        if window.scan_session.current_index == 0:
            window.log('[simulated] saved dark {}'.format(software.save_dark(role)))
        window.log('[simulated] saved {}'.format(software.save_spectrum(role, x_angle_deg, y_angle_deg)))

    return save_spectrum


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    connection = parser.add_mutually_exclusive_group(required=True)
    connection.add_argument('--port', help='serial port of the Arduino Uno, e.g. COM7 or /dev/ttyACM0')
    connection.add_argument('--simulate', action='store_true', help='run without hardware')
    parser.add_argument('--data-folder', help='folder the spectrometer software saves into')
    arguments = parser.parse_args()

    from angle_resolved_spectrometer.gui import SpectrometerWindow

    if arguments.simulate:
        controller = UnoMotorController(SimulatedUno(), pause_seconds=0.01, poll_interval_seconds=0.01)
    else:
        controller = UnoMotorController.open_port(arguments.port)
    instrument = AngleResolvedSpectrometer(controller, MELBOURNE_CALIBRATION)
    window = SpectrometerWindow(instrument, data_folder=arguments.data_folder)
    if arguments.simulate:
        window.on_point_reached = simulated_acquisition(window)
        window.log('Simulation mode: no hardware connected. Home first, choose a data folder, then scan.')
    window.mainloop()


if __name__ == '__main__':
    main()
