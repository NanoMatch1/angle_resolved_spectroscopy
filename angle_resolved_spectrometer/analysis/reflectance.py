'''Reflectance from sample and reference spectra.

For each sample spectrum S at angles (x, y), with reference (mirror) spectrum M
and dark spectra D_S and D_M::

    R(λ) = 100 % × (S − D_S) / (M − D_M) × (t_M / t_S)

where t are the integration times (the factor applies only with
``time_normalised=True``). R is relative to the mirror. For absolute
reflectance, multiply by the mirror's own reflectance curve (protected silver
is about 95-98 % across the visible).

Which reference goes with which sample
--------------------------------------
If a reference exists at exactly the sample's angles, it is used. Otherwise
``reference_axis = (sample_axis, reference_axis)`` picks one: the reference
whose angle on ``reference_axis`` equals the sample's angle on ``sample_axis``.
Axes are 0 for X (source) and 1 for Y (detector), or the letters.

The usual case is an uncoupled sample scan normalised against a specular
mirror scan. With the default ``(1, 1)``, the sample point (30, 45) uses the
mirror spectrum taken at (45, 45): the reference for each detector angle.
'''

import os

import numpy as np

from .file_organisation import DARK_FOLDER_NAME, SPECTRUM_EXTENSION
from .spectrum_files import SpectrumFile

_AXIS_INDEX = {'X': 0, 'Y': 1, 0: 0, 1: 1}


def axis_index(axis):
    '''0 for X / source arm, 1 for Y / detector arm.'''
    key = axis.upper() if isinstance(axis, str) else axis
    if key not in _AXIS_INDEX:
        raise ValueError("Axis must be 0, 1, 'X' or 'Y', got {!r}.".format(axis))
    return _AXIS_INDEX[key]


def _region_mask(wavelengths_nm, region_nm):
    mask = (wavelengths_nm >= region_nm[0]) & (wavelengths_nm <= region_nm[1])
    if not mask.any():
        raise ValueError('No data between {} and {} nm.'.format(*region_nm))
    return mask


class AngleReflectance:
    '''The spectra in one data folder, and the reflectance calculated from them.

    Attributes:
        spectra: {"reference" | "sample": {(x, y): SpectrumFile}}
        darks: {"reference" | "sample": SpectrumFile}
        reflectance: {(x, y): N x 2 array of wavelength (nm), reflectance (%)},
            filled by :meth:`calculate_reflectance`.
        warnings: messages about anything suspicious in the data.
    '''

    def __init__(self, data_folder, reference_axis=(1, 1), log=print):
        self.data_folder = data_folder
        self.sample_axis_index, self.reference_axis_index = (axis_index(axis) for axis in reference_axis)
        self.log = log
        self.warnings = []
        self.spectra = {'reference': {}, 'sample': {}}
        self.darks = {}
        self.darks_subtracted = False
        self.reflectance = {}
        self._load_spectra()
        self._load_darks()

    def _warn(self, message):
        self.warnings.append(message)
        self.log('Warning: ' + message)

    # --- loading ----------------------------------------------------------------

    def _load_spectra(self):
        for name in sorted(os.listdir(self.data_folder)):
            path = os.path.join(self.data_folder, name)
            if not (name.endswith(SPECTRUM_EXTENSION) and os.path.isfile(path)):
                continue
            try:
                spectrum = SpectrumFile(path)
            except ValueError as reason:
                self._warn('skipped {}: {}'.format(name, reason))
                continue
            if spectrum.is_dark:
                self._warn('{} is a dark spectrum outside {}; it was not used.'.format(name, DARK_FOLDER_NAME))
                continue
            if spectrum.angles in self.spectra[spectrum.role]:
                self._warn('two {} spectra at {}; using {}.'.format(spectrum.role, spectrum.angles, name))
            self.spectra[spectrum.role][spectrum.angles] = spectrum
        if not self.spectra['sample'] or not self.spectra['reference']:
            raise ValueError('{} needs both sample and reference spectra with angles in their names '
                             '(found {} sample, {} reference).'.format(
                                 self.data_folder, len(self.spectra['sample']), len(self.spectra['reference'])))

    def _load_darks(self):
        dark_folder = os.path.join(self.data_folder, DARK_FOLDER_NAME)
        if not os.path.isdir(dark_folder):
            return
        for name in sorted(os.listdir(dark_folder)):
            if not name.endswith(SPECTRUM_EXTENSION):
                continue
            dark = SpectrumFile(os.path.join(dark_folder, name))
            if dark.role in self.darks:
                self._warn('more than one {} dark; using {}.'.format(dark.role, name))
            self.darks[dark.role] = dark

    def summary(self):
        '''A short text report: what was loaded and which angles lack a partner.'''
        reference_angles = set(self.spectra['reference'])
        sample_angles = set(self.spectra['sample'])
        lines = ['{} reference and {} sample spectra; darks for: {}.'.format(
            len(reference_angles), len(sample_angles), ', '.join(sorted(self.darks)) or 'none')]
        if sample_angles - reference_angles:
            lines.append('Samples without a reference at the same angles (matched by reference_axis): {}'.format(
                sorted(sample_angles - reference_angles)))
        if reference_angles - sample_angles:
            lines.append('References without a sample: {}'.format(sorted(reference_angles - sample_angles)))
        return '\n'.join(lines)

    # --- processing ---------------------------------------------------------------

    def subtract_darks(self):
        '''Subtract each role's dark spectrum from that role's spectra (once only).'''
        if self.darks_subtracted:
            self._warn('darks were already subtracted; not subtracting again.')
            return
        for role, spectra_by_angles in self.spectra.items():
            dark = self.darks.get(role)
            if dark is None:
                self._warn('no {} dark spectrum; {} spectra are not dark-corrected.'.format(role, role))
                continue
            for spectrum in spectra_by_angles.values():
                if spectrum.integration_time_seconds != dark.integration_time_seconds:
                    self._warn('{} integration time {} s differs from its dark ({} s).'.format(
                        spectrum.filename, spectrum.integration_time_seconds, dark.integration_time_seconds))
                spectrum.data[:, 1] -= dark.counts
        self.darks_subtracted = True

    def find_reference(self, sample_angles):
        '''The reference spectrum for a sample point (see the module docstring).'''
        references = self.spectra['reference']
        if sample_angles in references:
            return references[sample_angles]
        wanted_angle = sample_angles[self.sample_axis_index]
        candidates = [angles for angles in references if angles[self.reference_axis_index] == wanted_angle]
        if not candidates:
            raise LookupError('No reference for sample at {}: none has {} on axis {}.'.format(
                sample_angles, wanted_angle, 'XY'[self.reference_axis_index]))
        if len(candidates) > 1:
            self._warn('several references fit sample {} ({}); using {}.'.format(
                sample_angles, sorted(candidates), candidates[0]))
        return references[candidates[0]]

    def calculate_reflectance(self, time_normalised=False):
        '''Fill :attr:`reflectance` with sample / reference × 100 for every sample point.

        time_normalised: correct for different integration times of sample and reference.
        '''
        self.reflectance = {}
        for sample_angles in sorted(self.spectra['sample']):
            sample = self.spectra['sample'][sample_angles]
            reference = self.find_reference(sample_angles)
            if not np.array_equal(sample.wavelengths_nm, reference.wavelengths_nm):
                raise ValueError('{} and {} have different wavelength axes.'.format(sample.filename, reference.filename))
            with np.errstate(divide='ignore', invalid='ignore'):
                ratio = sample.counts / reference.counts
            if time_normalised:
                if not (sample.integration_time_seconds and reference.integration_time_seconds):
                    raise ValueError('Integration time missing from {} or {}.'.format(sample.filename, reference.filename))
                ratio = ratio * reference.integration_time_seconds / sample.integration_time_seconds
            self.reflectance[sample_angles] = np.column_stack((sample.wavelengths_nm, ratio * 100))
        return self.reflectance

    def truncate(self, region_nm):
        '''Keep only wavelengths inside region_nm = (low, high).'''
        for angles, data in self.reflectance.items():
            self.reflectance[angles] = data[_region_mask(data[:, 0], region_nm)]
        return self.reflectance

    def normalise_reflectance(self, region_nm, normalisation_type='min'):
        '''Rescale each curve to 0-100.

        'min': the minimum is taken inside region_nm and the maximum over the whole curve.
        'max': the maximum is taken inside region_nm and the minimum over the whole curve.
        '''
        for data in self.reflectance.values():
            mask = _region_mask(data[:, 0], region_nm)
            lowest = np.min(data[mask, 1]) if normalisation_type == 'min' else np.min(data[:, 1])
            highest = np.max(data[mask, 1]) if normalisation_type == 'max' else np.max(data[:, 1])
            data[:, 1] = (data[:, 1] - lowest) / (highest - lowest) * 100
        return self.reflectance

    def normalise_reflectance_partial(self, region_nm, normalisation_type='min'):
        '''Use a region with no expected angle dependence as an internal reference.

        'min': subtract each curve's minimum in the region. 'max': scale each curve
        so its maximum in the region is 100. A stand-in when no absolute reference exists.
        '''
        for data in self.reflectance.values():
            mask = _region_mask(data[:, 0], region_nm)
            if normalisation_type == 'min':
                data[:, 1] -= np.min(data[mask, 1])
            elif normalisation_type == 'max':
                data[:, 1] = data[:, 1] / np.max(data[mask, 1]) * 100
            else:
                raise ValueError("normalisation_type must be 'min' or 'max'.")
        return self.reflectance

    def normalise_raw(self, region_nm):
        '''Rescale every raw spectrum to 0-100: the global minimum to 0, the maximum in region_nm to 100.'''
        for spectra_by_angles in self.spectra.values():
            for spectrum in spectra_by_angles.values():
                mask = _region_mask(spectrum.wavelengths_nm, region_nm)
                lowest = np.min(spectrum.counts)
                highest = np.max(spectrum.counts[mask])
                spectrum.data[:, 1] = (spectrum.counts - lowest) / (highest - lowest) * 100
        return self.spectra
