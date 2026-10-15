'''Reading spectra saved by Ocean Optics software (OceanView / SpectraSuite).

A saved spectrum is a text file: ``key: value`` header lines, then a line
``>>>>>Begin Spectral Data<<<<<``, then tab-separated wavelength (nm) and
counts. The file name says what was measured::

    reference_FLMS12345_45.0,45.0.txt      mirror, source arm 45 deg, detector arm 45 deg
    sample_FLMS12345_30.0,45.0.txt         sample, source arm 30 deg, detector arm 45 deg
    reference_dark_FLMS12345_0001.txt      dark spectrum for the reference run

The first underscore-separated part decides the role: if it contains "ref"
the file is a reference, otherwise a sample. Any name containing "dark" is a
dark spectrum.
'''

import os
import re

import numpy as np

BEGIN_DATA_MARKER = '>>>>>Begin Spectral Data<<<<<'
_DATA_SECTION_MARKER_PREFIX = '>>>>>'
_ANGLE_PAIR_PATTERN = re.compile(r'-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?')


def role_from_filename(filename):
    '''"reference" or "sample", from the first underscore-separated part of the name.'''
    first_part = filename.split('_')[0].lower()
    return 'reference' if 'ref' in first_part else 'sample'


def is_dark_filename(filename):
    return 'dark' in filename.lower()


def angles_from_filename(filename):
    '''The (x, y) angle pair written in a renamed file, or None if there is none.'''
    matches = _ANGLE_PAIR_PATTERN.findall(filename)
    if not matches:
        return None
    return tuple(float(angle) for angle in matches[-1].split(','))


def angle_label(angles):
    '''Short legend text: "45°" for specular points, "X 30°, Y 45°" otherwise.'''
    x_angle, y_angle = angles
    if x_angle == y_angle:
        return '{:g}°'.format(x_angle)
    return 'X {:g}°, Y {:g}°'.format(x_angle, y_angle)


class SpectrumFile:
    '''One saved spectrum: role, angles, header and a (wavelength, counts) array.'''

    def __init__(self, path):
        self.path = path
        self.filename = os.path.basename(path)
        self.role = role_from_filename(self.filename)
        self.is_dark = is_dark_filename(self.filename)
        self.angles = None if self.is_dark else angles_from_filename(self.filename)
        if not self.is_dark and self.angles is None:
            raise ValueError('No "x,y" angle pair in file name {!r}. Rename the files from the '
                             'scan list first.'.format(self.filename))
        self.header, self.data = read_spectrum_text(path)

    def __repr__(self):
        return 'SpectrumFile({!r}: {} {})'.format(self.filename, self.role, 'dark' if self.is_dark else self.angles)

    @property
    def wavelengths_nm(self):
        return self.data[:, 0]

    @property
    def counts(self):
        return self.data[:, 1]

    @property
    def integration_time_seconds(self):
        '''From the header; OceanView writes seconds, SpectraSuite microseconds. None if absent.'''
        if 'Integration Time (sec)' in self.header:
            return float(self.header['Integration Time (sec)'])
        if 'Integration Time (usec)' in self.header:
            return float(self.header['Integration Time (usec)']) * 1e-6
        return None


def read_spectrum_text(path):
    '''(header dict, N x 2 array) from an Ocean Optics text spectrum.'''
    header = {}
    rows = []
    in_data_section = False
    with open(path) as spectrum_file:
        for line in spectrum_file:
            if line.startswith(BEGIN_DATA_MARKER):
                in_data_section = True
                continue
            if line.startswith(_DATA_SECTION_MARKER_PREFIX) or not line.strip():
                continue
            if in_data_section:
                rows.append([float(value) for value in line.split('\t')[:2]])
            elif ':' in line:
                key, value = line.split(':', 1)
                header[key.strip()] = value.strip()
    if not in_data_section:
        raise ValueError('{} has no "{}" line; is it an Ocean Optics spectrum?'.format(path, BEGIN_DATA_MARKER))
    return header, np.array(rows)


def write_spectrum_text(path, wavelengths_nm, counts, integration_time_seconds):
    '''Write a spectrum in OceanView's layout (used by the simulator and tests).'''
    lines = ['Data from {} Node'.format(os.path.basename(path)), '',
             'Spectrometer: SIMULATED',
             'Integration Time (sec): {:E}'.format(integration_time_seconds),
             'Scans to average: 1',
             'XAxis mode: Wavelengths',
             'Number of Pixels in Spectrum: {}'.format(len(wavelengths_nm)),
             BEGIN_DATA_MARKER]
    lines += ['{:.3f}\t{:.2f}'.format(wavelength, count) for wavelength, count in zip(wavelengths_nm, counts)]
    with open(path, 'w') as spectrum_file:
        spectrum_file.write('\n'.join(lines) + '\n')
