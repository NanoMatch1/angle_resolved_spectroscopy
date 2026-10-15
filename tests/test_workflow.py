'''Whole-workflow tests: simulated instrument → data folder → analysis script → files.

These run the same steps an operator would, headless: home, a reference scan
and a sample scan (saving a spectrum at each point), then ``run_analysis.py``.
The simulated optics are known exactly, so the reflectance it reports can be
checked against the truth.
'''

import csv
import os
import subprocess
import sys

import numpy as np
import pytest

import run_analysis
from angle_resolved_spectrometer.demo import record_simulated_measurement, simulated_instrument
from angle_resolved_spectrometer.scans import specular_plan, uncoupled_plan
from angle_resolved_spectrometer.simulated_spectrometer import WAVELENGTHS_NM, thin_film_reflectance

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIRROR_REFLECTANCE = 0.97


def run_analysis_script(data_folder, *options):
    environment = dict(os.environ, MPLBACKEND='Agg')
    return subprocess.run([sys.executable, os.path.join(REPOSITORY_ROOT, 'run_analysis.py'), str(data_folder),
                           '--no-show', *options], capture_output=True, text=True, env=environment,
                          cwd=REPOSITORY_ROOT, check=True)


def read_csv_columns(path):
    with open(path) as csv_file:
        rows = list(csv.reader(csv_file))
    values = np.array(rows[1:], dtype=float)
    return rows[0], values


def test_specular_measurement_to_reflectance(tmp_path):
    record_simulated_measurement(str(tmp_path), log=lambda message: None)
    result = run_analysis_script(tmp_path, '--time-normalised', '--label', 'film')

    assert 'Renamed 10 files' in result.stdout
    exported = tmp_path / 'exported_data'
    assert {'film.png', 'film_stack.png', 'film_raw.png', 'reflectance_data_film.csv'} <= set(os.listdir(exported))

    header, values = read_csv_columns(exported / 'reflectance_data_film.csv')
    assert header[1:] == ['Reflectance X={0} Y={0} (%)'.format(angle) for angle in (20, 30, 40, 50, 60)]
    for column, angle in enumerate((20, 30, 40, 50, 60), start=1):
        expected_percent = 100 * thin_film_reflectance(WAVELENGTHS_NM, angle) / MIRROR_REFLECTANCE
        np.testing.assert_allclose(values[:, column], expected_percent, atol=0.5)

    rerun = run_analysis_script(tmp_path, '--time-normalised', '--label', 'film')
    assert 'already renamed' in rerun.stdout


def test_uncoupled_sample_against_specular_reference(tmp_path):
    plans = {'reference': specular_plan(30, 50, 10),
             'sample': uncoupled_plan('X', (30, 50, 10), (40, 40, 1))}
    record_simulated_measurement(str(tmp_path), plans_by_role=plans, log=lambda message: None)
    run_analysis_script(tmp_path, '--time-normalised', '--reference-axis', 'Y,Y', '--label', 'sweep')

    header, values = read_csv_columns(tmp_path / 'exported_data' / 'reflectance_data_sweep.csv')
    assert header[1:] == ['Reflectance X={} Y=40 (%)'.format(angle) for angle in (30, 40, 50)]
    specular_column = header.index('Reflectance X=40 Y=40 (%)')
    off_specular_column = header.index('Reflectance X=30 Y=40 (%)')
    assert values[:, specular_column].mean() > 50 * values[:, off_specular_column].mean()


def test_missing_scan_list_and_declined_prompt_stops_cleanly(tmp_path, monkeypatch):
    record_simulated_measurement(str(tmp_path), log=lambda message: None)
    os.remove(tmp_path / 'scan_list.json')
    monkeypatch.setattr('builtins.input', lambda prompt: 'n')
    with pytest.raises(SystemExit, match='Cannot rename'):
        run_analysis.prepare_folder(str(tmp_path), {'reference': 'reference', 'sample': 'sample'})


def test_missing_scan_list_can_be_written_from_the_prompt(tmp_path, monkeypatch, capsys):
    record_simulated_measurement(str(tmp_path), log=lambda message: None)
    os.remove(tmp_path / 'scan_list.json')
    answers = iter(['y', 'twenty', '20,60,10'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))
    run_analysis.prepare_folder(str(tmp_path), {'reference': 'reference', 'sample': 'sample'})
    assert 'sample_SIM00001_60.0,60.0.txt' in os.listdir(tmp_path)
    assert 'try again' in capsys.readouterr().out


def gui_available():
    try:
        import tkinter
        tkinter.Tk().destroy()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not gui_available(), reason='no display for Tk')
def test_gui_scan_with_simulated_acquisition(tmp_path):
    from angle_resolved_spectrometer.gui import SpectrometerWindow

    saved_points = []
    window = SpectrometerWindow(simulated_instrument(), data_folder=str(tmp_path),
                                on_point_reached=lambda role, x, y: saved_points.append((role, x, y)))
    try:
        window.instrument.home()
        window.mode.set('specular')
        window.scan_role.set('sample')
        for variable, value in zip(window.primary_range, (20, 40, 10)):
            variable.set(value)
        window.start_scan()
        window.next_point()
        window.next_point()
        window.next_point()
        assert saved_points == [('sample', 20, 20), ('sample', 30, 30), ('sample', 40, 40)]
        assert window.scan_session.is_finished
        assert (tmp_path / 'scan_list.json').exists()
    finally:
        window.destroy()
