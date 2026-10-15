'''Spectrum files, renaming, dark handling, reflectance and export.'''

import csv
import os

import numpy as np
import pytest

from angle_resolved_spectrometer.analysis import AngleReflectance, SpectrumFile, file_organisation
from angle_resolved_spectrometer.analysis.export_and_plots import export_reflectance_csv
from angle_resolved_spectrometer.analysis.spectrum_files import (angle_label, angles_from_filename,
                                                                 role_from_filename, write_spectrum_text)
from angle_resolved_spectrometer.scans import record_scan_plan, specular_plan

WAVELENGTHS_NM = np.array([500.0, 600.0, 700.0])


def write_spectrum(folder, name, counts, integration_time=0.1):
    path = os.path.join(folder, name)
    write_spectrum_text(path, WAVELENGTHS_NM, np.asarray(counts, dtype=float), integration_time)
    return path


def quiet_measurement(folder, **options):
    return AngleReflectance(str(folder), log=lambda message: None, **options)


# --- file names and parsing ----------------------------------------------------------

def test_filename_conventions():
    assert role_from_filename('reference_FLMS1_20.0,20.0.txt') == 'reference'
    assert role_from_filename('Ref-mirror_FLMS1_20.0,20.0.txt') == 'reference'
    assert role_from_filename('ITO_FLMS1_20.0,20.0.txt') == 'sample'
    assert angles_from_filename('sample_FLMS1_-5,40.5.txt') == (-5.0, 40.5)
    assert angles_from_filename('sample_FLMS1_0003.txt') is None
    assert angle_label((45.0, 45.0)) == '45°' and angle_label((30.0, 45.0)) == 'X 30°, Y 45°'


def test_reads_oceanview_text(tmp_path):
    spectrum = SpectrumFile(write_spectrum(tmp_path, 'sample_FLMS1_20.0,20.0.txt', [1, 2, 3], 0.5))
    assert spectrum.role == 'sample' and spectrum.angles == (20.0, 20.0)
    assert spectrum.integration_time_seconds == 0.5
    np.testing.assert_array_equal(spectrum.counts, [1, 2, 3])


def test_reads_spectrasuite_microseconds_and_footer(tmp_path):
    path = tmp_path / 'reference_X_30.0,30.0.txt'
    path.write_text('Integration Time (usec): 200000\n>>>>>Begin Spectral Data<<<<<\n'
                    '500.0\t10\n600.0\t20\n\n>>>>>End Spectral Data<<<<<\n')
    spectrum = SpectrumFile(str(path))
    assert spectrum.integration_time_seconds == pytest.approx(0.2)
    assert spectrum.data.shape == (2, 2)


def test_not_a_spectrum_is_reported(tmp_path):
    path = tmp_path / 'sample_X_30.0,30.0.txt'
    path.write_text('just notes\n')
    with pytest.raises(ValueError, match='Begin Spectral Data'):
        SpectrumFile(str(path))


# --- organising the folder -------------------------------------------------------------

def test_move_darks_ignores_folders(tmp_path):
    write_spectrum(tmp_path, 'sample_dark_FLMS1_0001.txt', [0, 0, 0])
    (tmp_path / 'dark_notes_folder').mkdir()
    assert file_organisation.move_darks(str(tmp_path)) == ['sample_dark_FLMS1_0001.txt']
    assert (tmp_path / 'darc_files' / 'sample_dark_FLMS1_0001.txt').exists()
    assert file_organisation.move_darks(str(tmp_path)) == []


def test_save_counter_and_new_name():
    assert file_organisation.save_counter('sample_FLMS1_0012.txt') == (12, 2)
    assert file_organisation.save_counter('thick_film_FLMS1_0003.txt') == (3, 3)
    assert file_organisation.angle_filename('sample_FLMS1_0012.txt', (30, 45)) == 'sample_FLMS1_30.0,45.0.txt'
    with pytest.raises(ValueError):
        file_organisation.save_counter('sample_FLMS1.txt')


def test_rename_follows_save_order_not_alphabetical(tmp_path):
    record_scan_plan(tmp_path, 'reference', specular_plan(20, 30, 10))
    record_scan_plan(tmp_path, 'sample', [(20, 40), (30, 40)])
    for counter in (9, 10):  # "10" sorts before "9" as text
        write_spectrum(tmp_path, 'reference_FLMS1_{}.txt'.format(counter), [1, 1, 1])
        write_spectrum(tmp_path, 'sample_FLMS1_{}.txt'.format(counter), [1, 1, 1])
    renames = dict(file_organisation.rename_files_by_scan_list(str(tmp_path)))
    assert renames['reference_FLMS1_9.txt'] == 'reference_FLMS1_20.0,20.0.txt'
    assert renames['sample_FLMS1_10.txt'] == 'sample_FLMS1_30.0,40.0.txt'
    assert file_organisation.rename_files_by_scan_list(str(tmp_path)) == []  # second run: nothing to do


def test_rename_refuses_count_mismatch_and_changes_nothing(tmp_path):
    record_scan_plan(tmp_path, 'sample', specular_plan(20, 40, 10))
    for counter in (1, 2):
        write_spectrum(tmp_path, 'sample_FLMS1_{:04d}.txt'.format(counter), [1, 1, 1])
    with pytest.raises(ValueError, match='2 sample files but 3 points'):
        file_organisation.rename_files_by_scan_list(str(tmp_path))
    assert sorted(os.listdir(tmp_path)) == ['sample_FLMS1_0001.txt', 'sample_FLMS1_0002.txt', 'scan_list.json']


def test_rename_without_scan_list_raises_file_not_found(tmp_path):
    write_spectrum(tmp_path, 'sample_FLMS1_0001.txt', [1, 1, 1])
    with pytest.raises(FileNotFoundError):
        file_organisation.rename_files_by_scan_list(str(tmp_path))


def test_half_renamed_folder_is_refused(tmp_path):
    record_scan_plan(tmp_path, 'sample', specular_plan(20, 30, 10))
    write_spectrum(tmp_path, 'sample_FLMS1_20.0,20.0.txt', [1, 1, 1])
    write_spectrum(tmp_path, 'sample_FLMS1_0002.txt', [1, 1, 1])
    with pytest.raises(ValueError, match='renamed and some are not'):
        file_organisation.rename_files_by_scan_list(str(tmp_path))


# --- reflectance -----------------------------------------------------------------------

def specular_folder(tmp_path, sample_time=0.1, reference_time=0.1, with_darks=True):
    write_spectrum(tmp_path, 'reference_F_20.0,20.0.txt', [110, 210, 410], reference_time)
    write_spectrum(tmp_path, 'sample_F_20.0,20.0.txt', [60, 60, 110], sample_time)
    if with_darks:
        (tmp_path / 'darc_files').mkdir()
        write_spectrum(tmp_path / 'darc_files', 'reference_dark_F_0001.txt', [10, 10, 10], reference_time)
        write_spectrum(tmp_path / 'darc_files', 'sample_dark_F_0001.txt', [10, 10, 10], sample_time)
    return tmp_path


def test_dark_corrected_reflectance(tmp_path):
    measurement = quiet_measurement(specular_folder(tmp_path))
    measurement.subtract_darks()
    measurement.subtract_darks()  # a second call must not subtract again
    reflectance = measurement.calculate_reflectance()[(20.0, 20.0)]
    np.testing.assert_allclose(reflectance[:, 1], [50, 25, 25])
    np.testing.assert_array_equal(reflectance[:, 0], WAVELENGTHS_NM)
    assert any('already subtracted' in warning for warning in measurement.warnings)


def test_time_normalisation_scales_by_reference_over_sample_time(tmp_path):
    measurement = quiet_measurement(specular_folder(tmp_path, sample_time=0.5, reference_time=0.1))
    measurement.subtract_darks()
    reflectance = measurement.calculate_reflectance(time_normalised=True)[(20.0, 20.0)]
    np.testing.assert_allclose(reflectance[:, 1], [10, 5, 5])


def test_missing_darks_are_a_warning_not_an_error(tmp_path):
    measurement = quiet_measurement(specular_folder(tmp_path, with_darks=False))
    measurement.subtract_darks()
    assert sum('no ' in warning and 'dark' in warning for warning in measurement.warnings) == 2


def uncoupled_folder(tmp_path):
    for angle, level in ((30, 100.0), (40, 200.0)):
        write_spectrum(tmp_path, 'reference_F_{0}.0,{0}.0.txt'.format(angle), [level] * 3)
    write_spectrum(tmp_path, 'sample_F_20.0,40.0.txt', [50.0] * 3)
    write_spectrum(tmp_path, 'sample_F_40.0,30.0.txt', [50.0] * 3)
    return tmp_path


def test_reference_axis_default_matches_detector_angle(tmp_path):
    reflectance = quiet_measurement(uncoupled_folder(tmp_path)).calculate_reflectance()
    assert reflectance[(20.0, 40.0)][0, 1] == pytest.approx(25)   # used reference (40, 40)
    assert reflectance[(40.0, 30.0)][0, 1] == pytest.approx(50)   # used reference (30, 30)


def test_reference_axis_can_match_source_angle(tmp_path):
    measurement = quiet_measurement(uncoupled_folder(tmp_path), reference_axis=('X', 'X'))
    assert measurement.find_reference((40.0, 30.0)).angles == (40.0, 40.0)
    with pytest.raises(LookupError, match='No reference'):
        measurement.find_reference((20.0, 40.0))   # no reference has X = 20


def test_folder_without_references_is_refused(tmp_path):
    write_spectrum(tmp_path, 'sample_F_20.0,20.0.txt', [1, 1, 1])
    with pytest.raises(ValueError, match='both sample and reference'):
        quiet_measurement(tmp_path)


def test_unrenamed_and_stray_files_are_skipped_with_warnings(tmp_path):
    specular_folder(tmp_path, with_darks=False)
    write_spectrum(tmp_path, 'sample_F_0007.txt', [1, 1, 1])
    measurement = quiet_measurement(tmp_path)
    assert list(measurement.spectra['sample']) == [(20.0, 20.0)]
    assert any('sample_F_0007.txt' in warning for warning in measurement.warnings)


def test_normalisations_and_truncation(tmp_path):
    measurement = quiet_measurement(specular_folder(tmp_path))
    measurement.subtract_darks()
    measurement.calculate_reflectance()                      # [50, 25, 25]
    measurement.normalise_reflectance_partial((550, 750), 'max')
    np.testing.assert_allclose(measurement.reflectance[(20.0, 20.0)][:, 1], [200, 100, 100])
    measurement.normalise_reflectance((450, 550), 'max')
    np.testing.assert_allclose(measurement.reflectance[(20.0, 20.0)][:, 1], [100, 0, 0])
    measurement.truncate((550, 750))
    assert measurement.reflectance[(20.0, 20.0)].shape == (2, 2)
    with pytest.raises(ValueError):
        measurement.truncate((100, 200))


def test_normalise_raw_rescales_spectra_in_place(tmp_path):
    measurement = quiet_measurement(specular_folder(tmp_path, with_darks=False))
    measurement.normalise_raw((550, 750))   # reference [110, 210, 410]: min 110, max in region 410
    np.testing.assert_allclose(measurement.spectra['reference'][(20.0, 20.0)].counts, [0, 100 / 3, 100])
    np.testing.assert_allclose(measurement.spectra['sample'][(20.0, 20.0)].counts, [0, 0, 100])


def test_csv_export(tmp_path):
    measurement = quiet_measurement(uncoupled_folder(tmp_path))
    path = export_reflectance_csv(measurement.calculate_reflectance(), str(tmp_path / 'out.csv'))
    with open(path) as csv_file:
        rows = list(csv.reader(csv_file))
    assert rows[0] == ['Wavelength (nm)', 'Reflectance X=20 Y=40 (%)', 'Reflectance X=40 Y=30 (%)']
    assert [float(value) for value in rows[1]] == [500.0, 25.0, 50.0]
