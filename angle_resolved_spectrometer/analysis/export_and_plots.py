'''Saving reflectance as CSV, and the standard plots.

matplotlib is imported inside the plotting functions, so the rest of the
package works without it.
'''

import csv
import os

import numpy as np

from .spectrum_files import angle_label

EXPORT_FOLDER_NAME = 'exported_data'


def default_export_folder(data_folder):
    folder = os.path.join(data_folder, EXPORT_FOLDER_NAME)
    os.makedirs(folder, exist_ok=True)
    return folder


def export_reflectance_csv(reflectance, path):
    '''One wavelength column, then one reflectance column per angle pair.'''
    angle_pairs = sorted(reflectance)
    wavelengths_nm = reflectance[angle_pairs[0]][:, 0]
    for angles in angle_pairs:
        if not np.array_equal(reflectance[angles][:, 0], wavelengths_nm):
            raise ValueError('Spectra at {} and {} have different wavelength axes.'.format(angle_pairs[0], angles))
    columns = [wavelengths_nm] + [reflectance[angles][:, 1] for angles in angle_pairs]
    header = ['Wavelength (nm)'] + ['Reflectance X={:g} Y={:g} (%)'.format(*angles) for angles in angle_pairs]
    with open(path, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)
        writer.writerows(np.column_stack(columns).tolist())
    return path


def _apply_limits(axis, wavelength_range_nm, reflectance_range_percent):
    if wavelength_range_nm:
        axis.set_xlim(*wavelength_range_nm)
    if reflectance_range_percent:
        axis.set_ylim(*reflectance_range_percent)


def plot_raw_spectra(spectra, save_path=None, show=True):
    '''Sample and reference counts side by side. spectra: AngleReflectance.spectra.'''
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 2, figsize=(10, 4), sharex=True)
    for axis, role in zip(axes, ('sample', 'reference')):
        for angles in sorted(spectra[role]):
            spectrum = spectra[role][angles]
            axis.plot(spectrum.wavelengths_nm, spectrum.counts, label=angle_label(angles))
        axis.set_title(role.capitalize())
        axis.set_xlabel('Wavelength (nm)')
        axis.set_ylabel('Counts')
        axis.legend(fontsize='small')
    figure.tight_layout()
    return _finish(figure, save_path, show)


def plot_reflectance(reflectance, title='', wavelength_range_nm=None, reflectance_range_percent=None,
                     save_path=None, show=True):
    '''All angles overlaid on one axis.'''
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(7, 5))
    colour_map = plt.get_cmap('plasma')
    angle_pairs = sorted(reflectance)
    for index, angles in enumerate(angle_pairs):
        data = reflectance[angles]
        axis.plot(data[:, 0], data[:, 1], label=angle_label(angles), color=colour_map(index / len(angle_pairs)))
    _apply_limits(axis, wavelength_range_nm, reflectance_range_percent)
    axis.set_xlabel('Wavelength (nm)')
    axis.set_ylabel('Reflectance (%)')
    axis.set_title(title)
    axis.legend(fontsize='small')
    figure.tight_layout()
    return _finish(figure, save_path, show)


def plot_reflectance_stack(reflectance, title='', wavelength_range_nm=None, reflectance_range_percent=None,
                           save_path=None, show=True):
    '''One panel per angle, stacked, sharing the wavelength axis.'''
    import matplotlib.pyplot as plt

    angle_pairs = sorted(reflectance)
    figure, axes = plt.subplots(len(angle_pairs), 1, figsize=(5, 1.4 * len(angle_pairs) + 1), sharex=True,
                                squeeze=False)
    colour_map = plt.get_cmap('plasma')
    for index, (axis, angles) in enumerate(zip(axes[:, 0], angle_pairs)):
        data = reflectance[angles]
        axis.plot(data[:, 0], data[:, 1], label=angle_label(angles), color=colour_map(index / len(angle_pairs)))
        axis.legend(loc='upper right', fontsize='small')
        _apply_limits(axis, wavelength_range_nm, reflectance_range_percent)
    axes[-1, 0].set_xlabel('Wavelength (nm)')
    axes[len(angle_pairs) // 2, 0].set_ylabel('Reflectance (%)')
    figure.suptitle(title)
    figure.tight_layout()
    return _finish(figure, save_path, show)


def _finish(figure, save_path, show):
    import matplotlib.pyplot as plt

    if save_path:
        figure.savefig(save_path, dpi=150)
    if show:
        plt.show()
    else:
        plt.close(figure)
    return save_path
