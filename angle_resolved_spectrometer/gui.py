'''Tkinter control window for the angle-resolved spectrometer.

The window only gathers input and shows state. Motion goes through
:class:`~angle_resolved_spectrometer.instrument.AngleResolvedSpectrometer` and
scans through :class:`~angle_resolved_spectrometer.scans.ScanSession`, which
are tested without a display.

Scans are semi-automatic: the window moves the arms to a point, the operator
records and saves a spectrum in the spectrometer software, then clicks
"Next point" (or presses Enter in the window).
'''

import tkinter as tk
from tkinter import filedialog, ttk

from . import scans

NO_FOLDER_TEXT = 'No folder selected'


class SpectrometerWindow(tk.Tk):

    def __init__(self, instrument, data_folder=None, on_point_reached=None):
        '''
        instrument: an AngleResolvedSpectrometer.
        data_folder: where scan_list.json is written; can also be chosen in the window.
        on_point_reached: optional callback(role, x_deg, y_deg) run at each scan point.
            The simulator uses it to "save" a spectrum automatically.
        '''
        super().__init__()
        self.instrument = instrument
        self.instrument.log = self.log
        self.on_point_reached = on_point_reached
        self.scan_session = None
        self.scan_role_of_session = None

        self.title('Angle-Resolved Spectrometer')
        self.geometry('900x760')

        self.data_folder = tk.StringVar(value=data_folder or NO_FOLDER_TEXT)
        self.mode = tk.StringVar(value='specular')
        self.scan_role = tk.StringVar(value='reference')
        self.primary_axis = tk.StringVar(value='X')
        self.x_angle = tk.DoubleVar(value=self.instrument.calibration.park_angle_deg)
        self.y_angle = tk.DoubleVar(value=self.instrument.calibration.park_angle_deg)
        self.polariser_turn_deg = tk.DoubleVar(value=90.0)
        self.primary_range = [tk.DoubleVar(value=value) for value in (20.0, 60.0, 5.0)]
        self.secondary_range = [tk.DoubleVar(value=value) for value in (45.0, 45.0, 5.0)]
        self.scan_status = tk.StringVar(value='No scan running.')

        self._build_instrument_frame()
        self._build_manual_frame()
        self._build_scan_frame()
        self._build_progress_frame()
        self._build_log()
        self.bind('<Return>', lambda event: self.next_point())
        self._show_mode_controls()

    # --- layout -------------------------------------------------------------------

    def _build_instrument_frame(self):
        frame = ttk.LabelFrame(self, text='Instrument', padding=8)
        frame.pack(padx=10, pady=5, fill='x')
        ttk.Button(frame, text='Home', command=lambda: self._run(self.instrument.home)).pack(side='left', padx=4)
        ttk.Button(frame, text='Read positions',
                   command=lambda: self._run(self.instrument.read_controller_angles)).pack(side='left', padx=4)
        ttk.Button(frame, text='Set positions to X/Y below', command=self.declare_positions).pack(side='left', padx=4)
        ttk.Label(frame, text='Data folder:').pack(side='left', padx=(20, 4))
        ttk.Entry(frame, textvariable=self.data_folder, width=36, state='readonly').pack(side='left')
        ttk.Button(frame, text='Browse', command=self.browse_folder).pack(side='left', padx=4)

    def _build_manual_frame(self):
        frame = ttk.LabelFrame(self, text='Manual control (degrees from vertical)', padding=8)
        frame.pack(padx=10, pady=5, fill='x')
        for column, (label, variable) in enumerate((('X source arm', self.x_angle), ('Y detector arm', self.y_angle))):
            ttk.Label(frame, text=label).grid(row=0, column=2 * column, padx=4)
            ttk.Entry(frame, textvariable=variable, width=8).grid(row=0, column=2 * column + 1, padx=4)
        ttk.Button(frame, text='Go', command=self.go_to_entered_angles).grid(row=0, column=4, padx=8)
        ttk.Label(frame, text='Turn polariser by').grid(row=0, column=5, padx=(20, 4))
        ttk.Entry(frame, textvariable=self.polariser_turn_deg, width=6).grid(row=0, column=6)
        ttk.Button(frame, text='Turn', command=lambda: self._run(
            self.instrument.rotate_polariser, self.polariser_turn_deg.get())).grid(row=0, column=7, padx=4)

    def _build_scan_frame(self):
        frame = ttk.LabelFrame(self, text='Scan setup', padding=8)
        frame.pack(padx=10, pady=5, fill='x')
        self.scan_frame = frame

        ttk.Label(frame, text='Mode').grid(row=0, column=0, sticky='w')
        for column, (text, value) in enumerate((('Specular (X = Y)', 'specular'), ('Uncoupled', 'uncoupled')), 1):
            ttk.Radiobutton(frame, text=text, variable=self.mode, value=value,
                            command=self._show_mode_controls).grid(row=0, column=column, sticky='w')

        ttk.Label(frame, text='Measuring').grid(row=1, column=0, sticky='w')
        for column, (text, value) in enumerate((('Reference (mirror)', 'reference'), ('Sample', 'sample')), 1):
            ttk.Radiobutton(frame, text=text, variable=self.scan_role, value=value).grid(
                row=1, column=column, sticky='w')

        self.primary_axis_label = ttk.Label(frame, text='Swept axis')
        self.primary_axis_buttons = [ttk.Radiobutton(frame, text=axis, variable=self.primary_axis, value=axis)
                                     for axis in ('X', 'Y')]

        self.primary_row_label = ttk.Label(frame, text='Angles: start / stop / step')
        self.secondary_row_label = ttk.Label(frame, text='Other axis: start / stop / step')
        self.primary_entries = [ttk.Entry(frame, textvariable=variable, width=7) for variable in self.primary_range]
        self.secondary_entries = [ttk.Entry(frame, textvariable=variable, width=7)
                                  for variable in self.secondary_range]
        self.primary_row_label.grid(row=3, column=0, sticky='w')
        for column, entry in enumerate(self.primary_entries, 1):
            entry.grid(row=3, column=column, padx=2, sticky='w')

        ttk.Button(frame, text='Start scan', command=self.start_scan).grid(row=5, column=0, pady=6, sticky='w')

    def _build_progress_frame(self):
        frame = ttk.LabelFrame(self, text='Scan progress', padding=8)
        frame.pack(padx=10, pady=5, fill='x')
        ttk.Label(frame, textvariable=self.scan_status).pack(side='left', padx=4)
        ttk.Button(frame, text='Stop scan', command=self.stop_scan).pack(side='right', padx=4)
        ttk.Button(frame, text='Next point  ⏎', command=self.next_point).pack(side='right', padx=4)

    def _build_log(self):
        frame = ttk.LabelFrame(self, text='Log', padding=8)
        frame.pack(padx=10, pady=5, fill='both', expand=True)
        self.log_text = tk.Text(frame, height=12, state='disabled')
        self.log_text.pack(fill='both', expand=True)

    def _show_mode_controls(self):
        uncoupled_widgets = ([(self.primary_axis_label, 2, 0)]
                             + [(button, 2, column) for column, button in enumerate(self.primary_axis_buttons, 1)]
                             + [(self.secondary_row_label, 4, 0)]
                             + [(entry, 4, column) for column, entry in enumerate(self.secondary_entries, 1)])
        for widget, row, column in uncoupled_widgets:
            if self.mode.get() == 'uncoupled':
                widget.grid(row=row, column=column, padx=2, sticky='w')
            else:
                widget.grid_remove()

    # --- actions ------------------------------------------------------------------

    def log(self, message):
        print(message)
        self.log_text.configure(state='normal')
        self.log_text.insert('end', message + '\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _run(self, action, *arguments):
        '''Run an instrument action, reporting failures in the log instead of crashing.'''
        try:
            return action(*arguments)
        except (ValueError, RuntimeError, OSError, tk.TclError) as error:
            self.log('Error: {}'.format(error))
            return None

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.data_folder.set(folder)

    def go_to_entered_angles(self):
        self._run(lambda: self.instrument.go_to_angles(self.x_angle.get(), self.y_angle.get()))

    def declare_positions(self):
        self._run(lambda: self.instrument.declare_current_angles(self.x_angle.get(), self.y_angle.get()))

    def current_plan(self):
        primary = [variable.get() for variable in self.primary_range]
        if self.mode.get() == 'specular':
            return scans.specular_plan(*primary)
        secondary = [variable.get() for variable in self.secondary_range]
        return scans.uncoupled_plan(self.primary_axis.get(), primary, secondary)

    def start_scan(self):
        if self.data_folder.get() == NO_FOLDER_TEXT:
            self.log('Choose the data folder (the one the spectrometer software saves into) first.')
            return
        if self.scan_session and not self.scan_session.is_finished:
            self.log('A scan is already running; stop it first.')
            return
        try:
            plan = self.current_plan()
            session = scans.ScanSession(self.instrument, plan)
            session.start()
        except (ValueError, RuntimeError, OSError, tk.TclError) as error:
            self.log('Scan not started: {}'.format(error))
            return
        self.scan_session = session
        self.scan_role_of_session = self.scan_role.get()
        path = scans.record_scan_plan(self.data_folder.get(), self.scan_role_of_session, plan)
        self.log('{} scan of {} points started; plan saved to {}.'.format(
            self.scan_role_of_session.capitalize(), len(plan), path))
        self._point_reached()

    def next_point(self):
        if self.scan_session is None or self.scan_session.is_finished:
            return
        if self._run(self.scan_session.advance):
            self._point_reached()
        elif self.scan_session.is_finished:
            self.scan_status.set(self.scan_session.progress_text)
            self.log('Scan complete; arms returned to the first point.')

    def stop_scan(self):
        if self.scan_session and not self.scan_session.is_finished:
            self.scan_session = None
            self.scan_status.set('Scan stopped.')
            self.log('Scan stopped. Spectra saved so far will not match the scan list; '
                     'delete them before re-running.')

    def _point_reached(self):
        self.scan_status.set(self.scan_session.progress_text)
        if self.on_point_reached:
            self.on_point_reached(self.scan_role_of_session, *self.scan_session.current_angles)
