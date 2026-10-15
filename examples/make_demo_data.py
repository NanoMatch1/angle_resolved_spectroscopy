'''Make a simulated data folder, then analyse it.

    python examples/make_demo_data.py demo_data
    python run_analysis.py demo_data --time-normalised

The simulated sample is a 400 nm transparent film on glass, so the reflectance
shows interference fringes that move to shorter wavelength as the angle grows.
'''

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from angle_resolved_spectrometer.demo import record_simulated_measurement  # noqa: E402

if __name__ == '__main__':
    data_folder = sys.argv[1] if len(sys.argv) > 1 else 'demo_data'
    os.makedirs(data_folder, exist_ok=True)
    record_simulated_measurement(data_folder, log=lambda message: None)
    print('Simulated measurement saved in {}. Next: python run_analysis.py {} --time-normalised'.format(
        data_folder, data_folder))
