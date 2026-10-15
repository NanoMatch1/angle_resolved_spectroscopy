'''A pretend spectrometer program that saves spectra the way OceanView does.

On the real instrument the operator saves each spectrum by hand; the files get
names like ``sample_FLMS12345_0003.txt``. This class writes files with the
same names and layout, so the whole workflow (scan, rename, analyse) can be
run and tested without hardware.

The "sample" is a transparent film on glass. Its reflectance shows thin-film
interference fringes that shift to shorter wavelength as the angle of
incidence grows, which is the kind of angle dependence the instrument measures.
'''

import os

import numpy as np

from .analysis.spectrum_files import write_spectrum_text

WAVELENGTHS_NM = np.linspace(400.0, 1000.0, 601)
DARK_LEVEL_COUNTS = 1000.0


def lamp_spectrum(wavelengths_nm):
    '''Counts per second from a halogen-like source through the fibres (arbitrary scale).'''
    peak_nm, width_nm = 650.0, 220.0
    return 4.0e5 * np.exp(-0.5 * ((wavelengths_nm - peak_nm) / width_nm) ** 2)


def thin_film_reflectance(wavelengths_nm, incidence_angle_deg, film_index=1.9,
                          film_thickness_nm=400.0, substrate_index=1.5):
    '''Unpolarised reflectance (0-1) of one film on a substrate, from the Airy formula.'''
    theta_air = np.radians(incidence_angle_deg)
    sin_air = np.sin(theta_air)
    cos_air = np.cos(theta_air)
    cos_film = np.sqrt(1 - (sin_air / film_index) ** 2)
    cos_substrate = np.sqrt(1 - (sin_air / substrate_index) ** 2)

    def fresnel_s(index_1, cos_1, index_2, cos_2):
        return (index_1 * cos_1 - index_2 * cos_2) / (index_1 * cos_1 + index_2 * cos_2)

    def fresnel_p(index_1, cos_1, index_2, cos_2):
        return (index_2 * cos_1 - index_1 * cos_2) / (index_2 * cos_1 + index_1 * cos_2)

    phase = 2 * np.pi * film_index * film_thickness_nm * cos_film / wavelengths_nm
    reflectances = []
    for fresnel in (fresnel_s, fresnel_p):
        top = fresnel(1.0, cos_air, film_index, cos_film)
        bottom = fresnel(film_index, cos_film, substrate_index, cos_substrate)
        amplitude = (top + bottom * np.exp(2j * phase)) / (1 + top * bottom * np.exp(2j * phase))
        reflectances.append(np.abs(amplitude) ** 2)
    return (reflectances[0] + reflectances[1]) / 2


def specular_overlap(x_angle_deg, y_angle_deg, acceptance_deg=1.5):
    '''How much specular light reaches the detector when the arms are mismatched.'''
    return np.exp(-0.5 * ((x_angle_deg - y_angle_deg) / acceptance_deg) ** 2)


class SimulatedSpectrometerSoftware:

    def __init__(self, data_folder, serial_number='SIM00001', mirror_reflectance=0.97,
                 integration_time_seconds=None, noise_seed=0):
        '''
        integration_time_seconds: {"reference": t, "sample": t}; the mirror is bright,
        so its default time is shorter.
        '''
        self.data_folder = data_folder
        self.serial_number = serial_number
        self.mirror_reflectance = mirror_reflectance
        self.integration_time_seconds = integration_time_seconds or {'reference': 0.1, 'sample': 0.5}
        self.random = np.random.default_rng(noise_seed)
        self._save_counters = {}

    def _next_filename(self, label):
        self._save_counters[label] = self._save_counters.get(label, 0) + 1
        return '{}_{}_{:04d}.txt'.format(label, self.serial_number, self._save_counters[label])

    def _save(self, label, counts, integration_time):
        noisy_counts = counts + self.random.normal(0.0, 5.0, counts.shape)
        path = os.path.join(self.data_folder, self._next_filename(label))
        write_spectrum_text(path, WAVELENGTHS_NM, noisy_counts, integration_time)
        return path

    def true_reflectance(self, role, x_angle_deg, y_angle_deg):
        '''The reflectance the simulated optics deliver at one arm geometry (0-1).'''
        overlap = specular_overlap(x_angle_deg, y_angle_deg)
        if role == 'reference':
            return np.full_like(WAVELENGTHS_NM, self.mirror_reflectance) * overlap
        return thin_film_reflectance(WAVELENGTHS_NM, x_angle_deg) * overlap

    def save_spectrum(self, role, x_angle_deg, y_angle_deg):
        '''What the operator does at each scan point: record and save one spectrum.'''
        integration_time = self.integration_time_seconds[role]
        signal = lamp_spectrum(WAVELENGTHS_NM) * integration_time * self.true_reflectance(
            role, x_angle_deg, y_angle_deg)
        return self._save(role, DARK_LEVEL_COUNTS + signal, integration_time)

    def save_dark(self, role):
        '''A dark spectrum (source blocked) at the role's integration time.'''
        return self._save('{}_dark'.format(role), np.full_like(WAVELENGTHS_NM, DARK_LEVEL_COUNTS),
                          self.integration_time_seconds[role])
