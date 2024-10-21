import tkinter as tk
from tkinter import ttk
import numpy as np
import time

class SpectrometerGUI(tk.Tk):
    def __init__(self, spectrometer):
        super().__init__()
        self.spectrometer = spectrometer
        self.title("Angle-Resolved Spectrometer Control")
        self.geometry("600x500")

        # Specular vs. Uncoupled mode
        self.mode = tk.StringVar(value="specular")
        self.create_mode_switch()

        # Angle control
        self.create_angle_control()

        # Scan setup with mutually exclusive axis selection and dynamic parameter display
        self.create_scan_setup()

        # Tree representation of scan configuration
        self.create_scan_tree()

    def create_mode_switch(self):
        mode_frame = ttk.LabelFrame(self, text="Measurement Mode", padding=(10, 10))
        mode_frame.pack(padx=10, pady=10, fill="x")

        specular_rb = ttk.Radiobutton(mode_frame, text="Specular", variable=self.mode, value="specular", command=self.update_mode)
        uncoupled_rb = ttk.Radiobutton(mode_frame, text="Uncoupled", variable=self.mode, value="uncoupled", command=self.update_mode)

        specular_rb.pack(side="left", padx=5, pady=5)
        uncoupled_rb.pack(side="left", padx=5, pady=5)

        home_button = ttk.Button(mode_frame, text="Home", command=self.spectrometer.home_motors)
        home_button.pack(side="right", padx=5, pady=5) # Add a home button to reset the motors

        show_motor_pos_button = ttk.Button(mode_frame, text="Show Motor Positions", command=self.spectrometer.get_current_position)
        show_motor_pos_button.pack(side="right", padx=5, pady=5) # Add a button to show the current motor positions

        set_motor_pos_button = ttk.Button(mode_frame, text="Set Motor Positions", command=self.set_motor_positions)
        set_motor_pos_button.pack(side="right", padx=5, pady=5) # Add a button to set the motor positions

    def create_angle_control(self):
        angle_frame = ttk.LabelFrame(self, text="Manual Angle Control", padding=(10, 10))
        angle_frame.pack(padx=10, pady=10, fill="x")

        self.x_angle = tk.DoubleVar()
        self.y_angle = tk.DoubleVar()

        x_label = ttk.Label(angle_frame, text="X Axis (deg):")
        x_entry = ttk.Entry(angle_frame, textvariable=self.x_angle, width=10)
        y_label = ttk.Label(angle_frame, text="Y Axis (deg):")
        y_entry = ttk.Entry(angle_frame, textvariable=self.y_angle, width=10)
        goto_button = ttk.Button(angle_frame, text="Goto", command=self.goto_angles)

        x_label.grid(row=0, column=0, padx=5, pady=5)
        x_entry.grid(row=0, column=1, padx=5, pady=5)
        y_label.grid(row=0, column=2, padx=5, pady=5)
        y_entry.grid(row=0, column=3, padx=5, pady=5)
        goto_button.grid(row=0, column=4, padx=5, pady=5)

    def create_file_saving(self):
        '''Create a frame for opening a browser to select a folder to save the data to'''
        self.file_frame = ttk.LabelFrame(self, text="File Saving", padding=(10, 10))
        self.file_frame.pack(padx=10, pady=10, fill="x")

        self.file_path = tk.StringVar()
        self.file_path.set("C:/Users/sjbrooke/OneDrive - The University of Melbourne/Data/Secondary/Sam Zaman/2024-08-05_BP/analysis")


    def create_scan_setup(self):
        self.scan_frame = ttk.LabelFrame(self, text="Scan Setup", padding=(10, 10))
        self.scan_frame.pack(padx=10, pady=10, fill="x")

        # Primary and Secondary Axis selection using mutually exclusive radio buttons
        self.primary_axis = tk.StringVar(value="X")
        self.secondary_axis = tk.StringVar(value="Y")

        primary_axis_label = ttk.Label(self.scan_frame, text="Primary Axis:")
        primary_x_rb = ttk.Radiobutton(self.scan_frame, text="X", variable=self.primary_axis, value="X", command=self.update_secondary_axis)
        primary_y_rb = ttk.Radiobutton(self.scan_frame, text="Y", variable=self.primary_axis, value="Y", command=self.update_secondary_axis)

        secondary_axis_label = ttk.Label(self.scan_frame, text="Secondary Axis:")
        self.secondary_x_rb = ttk.Radiobutton(self.scan_frame, text="X", variable=self.secondary_axis, value="X", state="normal")
        self.secondary_y_rb = ttk.Radiobutton(self.scan_frame, text="Y", variable=self.secondary_axis, value="Y", state="normal")

        primary_axis_label.grid(row=0, column=0, padx=5, pady=5)
        primary_x_rb.grid(row=0, column=1, padx=5, pady=5)
        primary_y_rb.grid(row=0, column=2, padx=5, pady=5)

        secondary_axis_label.grid(row=1, column=0, padx=5, pady=5)
        self.secondary_x_rb.grid(row=1, column=1, padx=5, pady=5)
        self.secondary_y_rb.grid(row=1, column=2, padx=5, pady=5)

        # Angle settings for the scan
        start_angle_label = ttk.Label(self.scan_frame, text="1 Start Angle (deg):")
        stop_angle_label = ttk.Label(self.scan_frame, text="1 Stop Angle (deg):")
        resolution_label = ttk.Label(self.scan_frame, text="1 Step Resolution (deg):")

        self.primary_start_angle = tk.DoubleVar()
        self.primary_stop_angle = tk.DoubleVar()
        self.primary_resolution = tk.DoubleVar()

        self.secondary_start_angle = tk.DoubleVar()
        self.secondary_stop_angle = tk.DoubleVar()
        self.secondary_resolution = tk.DoubleVar()

        # Trace changes in the angle values and update UI when edited
        self.primary_start_angle.trace_add("write", self.update_scan_tree)
        self.primary_stop_angle.trace_add("write", self.update_scan_tree)
        self.primary_resolution.trace_add("write", self.update_scan_tree)
        self.secondary_start_angle.trace_add("write", self.update_scan_tree)
        self.secondary_stop_angle.trace_add("write", self.update_scan_tree)
        self.secondary_resolution.trace_add("write", self.update_scan_tree)

        start_angle_entry = ttk.Entry(self.scan_frame, textvariable=self.primary_start_angle, width=10)
        stop_angle_entry = ttk.Entry(self.scan_frame, textvariable=self.primary_stop_angle, width=10)
        resolution_entry = ttk.Entry(self.scan_frame, textvariable=self.primary_resolution, width=10)

        start_angle_label.grid(row=2, column=0, padx=5, pady=5)
        start_angle_entry.grid(row=2, column=1, padx=5, pady=5)
        stop_angle_label.grid(row=2, column=2, padx=5, pady=5)
        stop_angle_entry.grid(row=2, column=3, padx=5, pady=5)
        resolution_label.grid(row=2, column=4, padx=5, pady=5)
        resolution_entry.grid(row=2, column=5, padx=5, pady=5)

        self.secondary_start_angle_entry = ttk.Entry(self.scan_frame, textvariable=self.secondary_start_angle, width=10)
        self.secondary_stop_angle_entry = ttk.Entry(self.scan_frame, textvariable=self.secondary_stop_angle, width=10)
        self.secondary_resolution_entry = ttk.Entry(self.scan_frame, textvariable=self.secondary_resolution, width=10)

        # Secondary row for uncoupled mode (initially hidden)
        self.secondary_start_angle_label = ttk.Label(self.scan_frame, text="2 Start Angle (deg):")
        self.secondary_stop_angle_label = ttk.Label(self.scan_frame, text="2 Stop Angle (deg):")
        self.secondary_resolution_label = ttk.Label(self.scan_frame, text="2 Step Resolution (deg):")

        start_scan_button = ttk.Button(self.scan_frame, text="Start Scan", command=self.start_scan)
        start_scan_button.grid(row=4, column=0, columnspan=6, pady=10)

        # Initially hide secondary axis controls
        self.toggle_secondary_axis_params(False)

    def create_scan_tree(self):
        tree_frame = ttk.LabelFrame(self, text="Scan Configuration", padding=(10, 10))
        tree_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.scan_tree = ttk.Treeview(tree_frame, columns=("Axis", "Start", "Stop", "Resolution"), show="headings")
        self.scan_tree.heading("Axis", text="Axis")
        self.scan_tree.heading("Start", text="Start Angle (deg)")
        self.scan_tree.heading("Stop", text="Stop Angle (deg)")
        self.scan_tree.heading("Resolution", text="Step Resolution (deg)")
        self.scan_tree.pack(fill="both", expand=True)

    def set_motor_positions(self):
        x_angle = self.x_angle.get()
        x_steps = self.spectrometer.angle_to_steps("X", x_angle)
        y_angle = self.y_angle.get()
        y_steps = self.spectrometer.angle_to_steps("Y", y_angle)

        print(f"Setting X axis to {x_angle}° and Y axis to {y_angle}°")
        # Z is not yet implemented
        self.spectrometer.set_motor_positions(x_steps, y_steps, 0)

    def update_scan_tree(self, *args):
        self.scan_tree.delete(*self.scan_tree.get_children())
        # Update the scan tree with the selected scan configuration
        if self.mode.get() == "specular":
            self.scan_tree.insert("", "end", values=("X/Y", self.primary_start_angle.get(), self.primary_stop_angle.get(), self.primary_resolution.get()))
        if self.mode.get() == "uncoupled":
            self.scan_tree.insert("", "end", values=(self.primary_axis.get(), self.primary_start_angle.get(), self.primary_stop_angle.get(), self.primary_resolution.get()))
            self.scan_tree.insert("", "end", values=(self.secondary_axis.get(), self.secondary_start_angle.get(), self.secondary_stop_angle.get(), self.secondary_resolution.get()))

    def update_mode(self):
        mode = self.mode.get()
        print(f"Switched to {mode} mode.")
        if mode == "uncoupled":
            self.toggle_secondary_axis_params(True)
        else:
            self.toggle_secondary_axis_params(False)

    def update_secondary_axis(self):
        primary = self.primary_axis.get()

        # Disable the secondary axis option corresponding to the primary axis
        if primary == "X":
            self.secondary_x_rb.config(state="disabled")
            self.secondary_y_rb.config(state="normal")
            self.secondary_axis.set("Y")
        else:
            self.secondary_x_rb.config(state="normal")
            self.secondary_y_rb.config(state="disabled")
            self.secondary_axis.set("X")

    def toggle_secondary_axis_params(self, show):
        """Show or hide secondary axis parameters."""
        if show:
            self.secondary_start_angle_label.grid(row=3, column=0, padx=5, pady=5)
            self.secondary_start_angle_entry.grid(row=3, column=1, padx=5, pady=5)
            self.secondary_stop_angle_label.grid(row=3, column=2, padx=5, pady=5)
            self.secondary_stop_angle_entry.grid(row=3, column=3, padx=5, pady=5)
            self.secondary_resolution_label.grid(row=3, column=4, padx=5, pady=5)
            self.secondary_resolution_entry.grid(row=3, column=5, padx=5, pady=5)
        else:
            self.secondary_start_angle_label.grid_remove()
            self.secondary_start_angle_entry.grid_remove()
            self.secondary_stop_angle_label.grid_remove()
            self.secondary_stop_angle_entry.grid_remove()
            self.secondary_resolution_label.grid_remove()
            self.secondary_resolution_entry.grid_remove()

    def goto_angles(self):
        x = self.x_angle.get()
        y = self.y_angle.get()
        print(f"Moving to X: {x} deg, Y: {y} deg")
        self.update_scan_tree()
        self.spectrometer.go_to_angle(x, y)

    def start_scan(self):
        primary = self.primary_axis.get()
        secondary = self.secondary_axis.get()
        primary_start = self.primary_start_angle.get()
        primary_stop = self.primary_stop_angle.get()
        primary_resolution = self.primary_resolution.get()
        primary_parameters = (primary_start, primary_stop, primary_resolution)

        if self.mode.get() == "specular":
            self.run_specular_scan(primary_start, primary_stop, primary_resolution)
        elif self.mode.get() == "uncoupled":
            secondary_start = self.secondary_start_angle.get()
            secondary_stop = self.secondary_stop_angle.get()
            secondary_resolution = self.secondary_resolution.get()
            secondary_parameters = (secondary_start, secondary_stop, secondary_resolution)

            self.run_uncoupled_scan(primary_parameters, secondary_parameters)

    def generate_scan_dimensions(self, primary_parameters, secondary_parameters, axis_order):
        # Generate the scan dimensions based on the primary and secondary axis
        primary_angles = np.arange(primary_parameters[0], primary_parameters[1]+primary_parameters[2], primary_parameters[2])
        secondary_angles = np.arange(secondary_parameters[0], secondary_parameters[1]+secondary_parameters[2], secondary_parameters[2])

        flattened_angles = []

        for i, secondary_angle in enumerate(secondary_angles):
            for j, primary_angle in enumerate(primary_angles):
                if axis_order == ("X", "Y"):
                    flattened_angles.append((primary_angle, secondary_angle))
                elif axis_order == ("Y", "X"):
                    flattened_angles.append((secondary_angle, primary_angle))

        return flattened_angles

    def run_specular_scan(self, start, stop, resolution):
        print(f"Running specular scan from {start}° to {stop}° with resolution {resolution}°.")

        print("Scan to commense:")
        print(f"Angles: {np.arange(start, stop+resolution, resolution)}")
        input("Press Enter to start the scan...")

        for angle in np.arange(start, stop+resolution, resolution):
            self.spectrometer.go_to_angle(angle, angle)
            self.spectrometer.wait_for_motors()
            input("Press Enter to continue to next angle...")

        self.spectrometer.go_to_angle(start, start)  # Return to the origin
        print("Scan complete.")

    def run_uncoupled_scan(self, primary_parameters, secondary_parameters):
        p_start, p_stop, p_res = primary_parameters
        s_start, s_stop, s_res = secondary_parameters
        axis_order = (self.primary_axis.get(), self.secondary_axis.get())
        scan_list = self.generate_scan_dimensions(primary_parameters, secondary_parameters, axis_order)
        
        print(f"Running uncoupled scan with primary axis from {p_start}° to {p_stop}° and secondary axis from {s_start}° to {s_stop}°.")
        # primary_angles = np.arange(p_start, p_stop+p_res, p_res)
        # secondary_angles = np.arange(s_start, s_stop+s_res, s_res)

        print("Scan to commense:")
        print(scan_list)
        input("Press Enter to start the scan...")

        self.export_scan_list(scan_list, "scan_list.txt") # Export the scan list to a file, 

        # for sec_angle in np.arange(s_start, s_stop+s_res, s_res):
        #     pri_angle = p_start
        #     self.spectrometer.go_to_angle(pri_angle, sec_angle) 

        #     for pri_angle in np.arange(p_start, p_stop+p_res, p_res):
        #         self.spectrometer.go_to_angle(pri_angle, sec_angle)  
        #         self.spectrometer.wait_for_motors()
        #         input("Press Enter to continue to next primary axis angle...")

        for primary_angle, secondary_angle in scan_list:
            self.spectrometer.go_to_angle(primary_angle, secondary_angle)
            self.spectrometer.wait_for_motors()
            input("Press Enter to continue to next angle...")

        self.spectrometer.go_to_angle(p_start, s_start)  # Return to the origin
        print("Scan complete.")
    
    def export_scan_list(self, scan_list, filename):
        with open(filename, "w") as f:
            for primary_angle, secondary_angle in scan_list:
                f.write(f"{primary_angle},{secondary_angle}\n")

# For testing purposes, we'll create a dummy Spectrometer class
class DummySpectrometer:
    def go_to_angle(self, x, y):
        if x is None:
            print(f"Moving Y axis to {y}°")
        elif y is None:
            print(f"Moving X axis to {x}°")
        else:
            print(f"Moving X axis to {x}° and Y axis to {y}°")

# Instantiate the GUI with the dummy spectrometer
if __name__ == "__main__":
    spectrometer = DummySpectrometer()
    app = SpectrometerGUI(spectrometer)
    app.mainloop()
