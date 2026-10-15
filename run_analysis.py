'''Turn a folder of saved spectra into reflectance plots and a CSV.

    python run_analysis.py PATH/TO/DATA --time-normalised --wavelength-range 440,1000

Steps: move dark spectra into darc_files/, rename the spectrometer's files with
their angles (from scan_list.json), subtract darks, divide sample by reference,
then save plots and reflectance_<label>.csv in exported_data/.
'''

import argparse
import os

from angle_resolved_spectrometer.analysis import AngleReflectance, move_darks, rename_files_by_scan_list
from angle_resolved_spectrometer.analysis import export_and_plots
from angle_resolved_spectrometer.scans import SCAN_LIST_FILENAME, record_specular_scan_list


def number_pair(text):
    first, second = text.split(',')
    return float(first), float(second)


def axis_pair(text):
    return tuple(part.strip() for part in text.split(','))


def offer_to_write_scan_list(data_folder):
    '''Ask for the specular scan range when scan_list.json is missing. Returns True if written.'''
    answer = input('{} not found. Were reference and sample both specular scans over the same angles? '
                   '(y/n): '.format(SCAN_LIST_FILENAME))
    if answer.strip().lower() != 'y':
        return False
    while True:
        text = input('Enter start,stop,step in degrees (e.g. 20,60,5): ')
        try:
            start, stop, step = (float(value) for value in text.split(','))
            plan = record_specular_scan_list(data_folder, start, stop, step)
        except ValueError as error:
            print('Not understood ({}); try again.'.format(error))
            continue
        print('Wrote {} with {} points.'.format(SCAN_LIST_FILENAME, len(plan)))
        return True


def prepare_folder(data_folder, role_identifiers):
    moved = move_darks(data_folder)
    if moved:
        print('Moved {} dark spectra into darc_files/.'.format(len(moved)))
    try:
        renamed = rename_files_by_scan_list(data_folder, role_identifiers)
    except FileNotFoundError:
        if not offer_to_write_scan_list(data_folder):
            raise SystemExit('Cannot rename files without {}. Stopping.'.format(SCAN_LIST_FILENAME))
        renamed = rename_files_by_scan_list(data_folder, role_identifiers)
    print('Renamed {} files with their angles.'.format(len(renamed)) if renamed else 'Files already renamed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('data_folder')
    parser.add_argument('--label', help='name used in plot titles and output files (default: folder name)')
    parser.add_argument('--reference-axis', type=axis_pair, default=('Y', 'Y'),
                        help='sample axis,reference axis used to match references to samples (default Y,Y)')
    parser.add_argument('--reference-identifier', default='reference', help='text in reference file names')
    parser.add_argument('--sample-identifier', default='sample', help='text in sample file names')
    parser.add_argument('--time-normalised', action='store_true',
                        help='correct for different sample and reference integration times')
    parser.add_argument('--wavelength-range', type=number_pair, help='low,high in nm, e.g. 440,1000')
    parser.add_argument('--reflectance-range', type=number_pair, help='plot y-limits low,high in %%')
    parser.add_argument('--no-show', action='store_true', help='save plots without opening windows')
    arguments = parser.parse_args()

    data_folder = arguments.data_folder
    label = arguments.label or os.path.basename(os.path.normpath(data_folder))
    prepare_folder(data_folder, {'reference': arguments.reference_identifier,
                                 'sample': arguments.sample_identifier})

    measurement = AngleReflectance(data_folder, reference_axis=arguments.reference_axis)
    print(measurement.summary())
    measurement.subtract_darks()
    measurement.calculate_reflectance(time_normalised=arguments.time_normalised)
    if arguments.wavelength_range:
        measurement.truncate(arguments.wavelength_range)

    export_folder = export_and_plots.default_export_folder(data_folder)
    show = not arguments.no_show
    export_and_plots.plot_raw_spectra(measurement.spectra, os.path.join(export_folder, label + '_raw.png'), show)
    plot_options = dict(title=label, wavelength_range_nm=arguments.wavelength_range,
                        reflectance_range_percent=arguments.reflectance_range, show=show)
    export_and_plots.plot_reflectance(measurement.reflectance,
                                      save_path=os.path.join(export_folder, label + '.png'), **plot_options)
    export_and_plots.plot_reflectance_stack(measurement.reflectance,
                                            save_path=os.path.join(export_folder, label + '_stack.png'),
                                            **plot_options)
    csv_path = export_and_plots.export_reflectance_csv(
        measurement.reflectance, os.path.join(export_folder, 'reflectance_data_{}.csv'.format(label)))
    print('Saved plots and {} in {}'.format(os.path.basename(csv_path), export_folder))


if __name__ == '__main__':
    main()
