'''Turning the spectrometer software's file names into angle-labelled ones.

The spectrometer software saves files as ``<label>_<serial>_<counter>.txt``
with a counter that increases with each save. Because spectra are saved in
scan-plan order, the n-th reference file belongs to the n-th reference point
in ``scan_list.json`` (and likewise for samples). Renaming replaces the
counter with the angles: ``reference_FLMS12345_0003.txt`` becomes
``reference_FLMS12345_30.0,30.0.txt``.

Dark spectra are moved into the ``darc_files`` subfolder first. The folder
name is misspelt, but existing data folders use it, so it stays.
'''

import os

from ..scans import read_scan_list
from .spectrum_files import angles_from_filename, is_dark_filename

DARK_FOLDER_NAME = 'darc_files'
SPECTRUM_EXTENSION = '.txt'


def move_darks(data_folder):
    '''Move dark spectra into ``darc_files``. Returns the names moved.'''
    dark_names = [name for name in sorted(os.listdir(data_folder))
                  if is_dark_filename(name) and os.path.isfile(os.path.join(data_folder, name))]
    if not dark_names:
        return []
    dark_folder = os.path.join(data_folder, DARK_FOLDER_NAME)
    os.makedirs(dark_folder, exist_ok=True)
    for name in dark_names:
        os.rename(os.path.join(data_folder, name), os.path.join(dark_folder, name))
    return dark_names


def save_counter(filename):
    '''The save counter in a spectrometer file name: its last all-digit "_" field.'''
    stem = os.path.splitext(filename)[0]
    fields = stem.split('_')
    for position in range(len(fields) - 1, 0, -1):
        if fields[position].isdigit():
            return int(fields[position]), position
    raise ValueError('No save counter in file name {!r}.'.format(filename))


def angle_filename(filename, angles):
    '''The new name: everything before the counter, then "_x,y.txt".'''
    _, counter_position = save_counter(filename)
    fields = os.path.splitext(filename)[0].split('_')
    angle_tag = '{},{}'.format(float(angles[0]), float(angles[1]))
    return '_'.join(fields[:counter_position] + [angle_tag]) + SPECTRUM_EXTENSION


def _spectrum_names(data_folder, identifier):
    return [name for name in os.listdir(data_folder)
            if name.endswith(SPECTRUM_EXTENSION) and identifier in name and not is_dark_filename(name)]


def plan_renames(data_folder, role_identifiers=None):
    '''Work out every rename without touching the files.

    role_identifiers: {"reference": text in reference file names, "sample": text in
    sample file names}; defaults to the role names themselves.
    Returns [(old name, new name), ...]. Roles whose files are all renamed
    already are skipped. Raises ValueError if the file count and the scan list
    disagree, or if a role is half renamed.
    '''
    role_identifiers = role_identifiers or {'reference': 'reference', 'sample': 'sample'}
    renames = []
    scan_list = None
    for role, identifier in role_identifiers.items():
        names = _spectrum_names(data_folder, identifier)
        unrenamed = [name for name in names if angles_from_filename(name) is None]
        if not unrenamed:
            continue
        if len(unrenamed) != len(names):
            raise ValueError('Some {} files are renamed and some are not; sort the folder out by hand.'.format(role))
        if scan_list is None:
            scan_list = read_scan_list(data_folder)
        if role not in scan_list:
            raise ValueError('scan_list.json has no "{}" plan.'.format(role))
        plan = scan_list[role]
        if len(unrenamed) != len(plan):
            raise ValueError('{} {} files but {} points in the scan list. Was a spectrum saved twice, '
                             'or missed?'.format(len(unrenamed), role, len(plan)))
        in_save_order = sorted(unrenamed, key=lambda name: save_counter(name)[0])
        renames += [(name, angle_filename(name, angles)) for name, angles in zip(in_save_order, plan)]
    return renames


def rename_files_by_scan_list(data_folder, role_identifiers=None):
    '''Rename the spectrometer's files with their angles. Returns the (old, new) pairs.

    Raises FileNotFoundError if renaming is needed but ``scan_list.json`` is missing.
    '''
    renames = plan_renames(data_folder, role_identifiers)
    for old_name, new_name in renames:
        if os.path.exists(os.path.join(data_folder, new_name)):
            raise FileExistsError('{} already exists; refusing to overwrite it.'.format(new_name))
    for old_name, new_name in renames:
        os.rename(os.path.join(data_folder, old_name), os.path.join(data_folder, new_name))
    return renames
