import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

def rename_files(dataDir):
    reference_files = [file for file in os.listdir(dataDir) if 'reference' in file]
    sample_files = [file for file in os.listdir(dataDir) if 'sample' in file]
    sorted_reference_files = sorted(reference_files, key=lambda x: int(x.split('_')[3].split('.')[0]))
    sorted_sample_files = sorted(sample_files, key=lambda x: int(x.split('_')[3].split('.')[0]))

    angle_list = []

    with open(os.path.join(dataDir, 'scan_list.dat'), 'r') as file:
        lines = file.readlines()
        for line in lines:
            line = line.strip()
            angle_list.append(line.split(','))

    for idx, angles in enumerate(angle_list):
        reference_rename = sorted_reference_files[idx].split('_')
        reference_rename = '_'.join(reference_rename[:-1]) + f"_{angles[0]}.txt"
        sample_rename = sorted_sample_files[idx].split('_')
        sample_rename = '_'.join(sample_rename[:-1]) + f"_{angles[0]}.txt"

        os.rename(os.path.join(dataDir, sorted_reference_files[idx]), os.path.join(dataDir, reference_rename))
        os.rename(os.path.join(dataDir, sorted_sample_files[idx]), os.path.join(dataDir, sample_rename))

    print("Files renamed.")

class ReflectionFile:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.data_type, self.angle = self._parse_filename(self.filename)
        self.header = {}
        self.data = None
        self.load_file()

    def _parse_filename(self, filename):
        name_parts = filename[:-4].split('_')
        data_type = name_parts[1]
        angle = float(name_parts[3].split('.')[0])
        # breakpoint()
        return data_type, angle

    def load_file(self):
        with open(self.filepath, 'r') as file:
            lines = file.readlines()

        header_lines = []
        data_lines = []
        found_data = False

        for line in lines:
            if line.startswith('>>>>>Begin Spectral Data<<<<<'):
                found_data = True
                continue

            if found_data:
                data_lines.append(line)
            else:
                header_lines.append(line)

        self.header = self._parse_header(header_lines)
        self.data = self._parse_data(data_lines)

    def _parse_header(self, header_lines):
        header = {}
        for line in header_lines:
            if ':' in line:
                key, value = line.split(':', 1)
                header[key.strip()] = value.strip()
        return header

    def _parse_data(self, data_lines):
        data = [list(map(float, line.split('\t'))) for line in data_lines]
        return np.array(data)

    @property
    def integration_time(self):
        return float(self.header.get('Integration Time (sec)', 0))

class AngleReflectance:
    def __init__(self, fileDir):
        self.fileDir = fileDir
        self.files = self.load_data()
        self.sample_identifier = 'sample'
        self.reference_identifier = 'reference'
        self.identifier = None

    def load_data(self):
        files = [os.path.join(self.fileDir, file) for file in os.listdir(self.fileDir) if file.endswith('.txt')]
        reflection_files = [ReflectionFile(file) for file in files]

        angle_dict = {}
        for file in reflection_files:
            if file.data_type not in angle_dict:
                angle_dict[file.data_type] = {}
            angle_dict[file.data_type][file.angle] = file

        return angle_dict

    def calculate_reflectivity(self, reference_identifier=None, sample_identifier=None, time_normalised=False):
        '''Calculates the reflectivity of the sample using the reference data. If time_normalised is True, the reflectance is normalised by the integration time of the sample.'''

        if reference_identifier is None:
            reference_identifier = self.reference_identifier
        if sample_identifier is None:
            sample_identifier = self.sample_identifier
        
        reference_dict = self.files[reference_identifier]
        sample_dict = self.files[sample_identifier]
        self.reflectance_dict = {}

        for angle in sample_dict:
            sample_data = sample_dict[angle].data
            reference_data = reference_dict[angle].data
            reflectance_data = sample_data[:, 1] / reference_data[:, 1]

            if time_normalised is True:
                # Handle different integration times if needed
                integration_time_ratio = sample_dict[angle].integration_time / reference_dict[angle].integration_time
                reflectance_data *= integration_time_ratio

            reflectance_data *= 100  # Convert to percentage
            # reflectance_data /= 2 # the data is doubled for some reason, possibly normalisation time #TODO: Fix this Its from the integration time of 0.5s... but the ratios should be the same...
            self.reflectance_dict[angle] = np.column_stack((sample_data[:, 0], reflectance_data))

        return self.reflectance_dict

    def plot_raw(self, offset=0):
        label_1, label_2 = list(self.files.keys())[:2]
        key_dict_1 = self.files[label_1]
        key_dict_2 = self.files[label_2]

        fig, ax = plt.subplots(1, 2)

        for idx, (angle, file) in enumerate(key_dict_1.items()):
            ax[0].plot(file.data[:, 0], file.data[:, 1] + offset * idx, label=f"{angle}°")
        ax[0].set_title(label_1)
        ax[0].set_xlabel('Wavelength (nm)')
        ax[0].set_ylabel('Intensity (a.u.)')
        ax[0].legend()

        for idx, (angle, file) in enumerate(key_dict_2.items()):
            ax[1].plot(file.data[:, 0], file.data[:, 1] + offset * idx, label=f"{angle}°")
        ax[1].set_title(label_2)
        ax[1].set_xlabel('Wavelength (nm)')
        ax[1].set_ylabel('Intensity (a.u.)')
        ax[1].legend()

        plt.show()

    def plot_reflectance(self, xregion=None, yregion=None, title=None, exportDir=None, save_plot=True):
        if title is None:
            title = self.identifier
        for angle, data in self.reflectance_dict.items():
            plt.plot(data[:, 0], data[:, 1], label=f"{angle}°")

        if xregion:
            plt.xlim(*xregion)
        if yregion:
            plt.ylim(*yregion)

        plt.xlabel('Wavelength (nm)')
        plt.ylabel('Reflectance percentage (%)')
        plt.title(title)
        plt.legend()

        if save_plot == True:
            if exportDir is None:
                exportDir = os.path.join(self.fileDir, 'exported_data')
            plt.savefig(os.path.join(exportDir, f"{self.identifier}.png"))
        plt.show()

    def plot_reflectance_individual(self, xregion=None, yregion=None, title=None, exportDir=None, save_plot=True):
        '''Makes a subplots for each angle in the reflectance data.'''
        if title is None:
            title = self.identifier
        fig, ax = plt.subplots(len(self.reflectance_dict), 1, figsize=(5, 10), sharex=True, sharey=False)

        cmap = plt.get_cmap('plasma')

        for idx, (angle, data) in enumerate(self.reflectance_dict.items()):
            # ax[idx].plot(data[:, 0], data[:, 1], label=f"{angle}°")
            ax[idx].plot(data[:, 0], data[:, 1], label=f"{angle}°", color=cmap(idx / len(self.reflectance_dict)))
            # ax[idx].set_title(f"{angle}°")
            # ax[idx].set_xlabel('Wavelength (nm)')
            if idx == len(self.reflectance_dict) - 1:
                ax[idx].set_xlabel('Wavelength (nm)')
            if idx == len(self.reflectance_dict) // 2:
                ax[idx].set_ylabel('Reflectance percentage (%)')
            ax[idx].legend()

            # ax[idx].set_xlim(min(data[:, 0]), max(data[:, 0]))

            if xregion:
                for idx in range(len(ax)):
                    ax[idx].set_xlim(*xregion)
            
            if yregion:
                for idx in range(len(ax)):
                    ax[idx].set_ylim(*yregion)

            else:
                ax[idx].set_ylim(min(data[:, 1])/1.01, max(data[:, 1])*1.01)

        plt.suptitle(title)
        plt.tight_layout()
        plt.subplots_adjust(top=0.95, hspace=0.1)

        if save_plot == True:
            if exportDir is None:
                exportDir = os.path.join(self.fileDir, 'exported_data')
            plt.savefig(os.path.join(exportDir, f"{self.identifier}_individual.png"))
        plt.show()


    def plot_original(self):
        data_dict = self.files['sample']
        ref_dict = self.files['reference']

        fig, ax = plt.subplots(2, 1)

        for angle, file in data_dict.items():
            ax[0].plot(file.data[:, 0], file.data[:, 1], label=f"{angle}°")
        for angle, file in ref_dict.items():
            ax[1].plot(file.data[:, 0], file.data[:, 1], label=f"{angle}°")

        ax[0].set_title('Sample')
        ax[1].set_title('Reference')
        ax[0].legend()
        ax[1].legend()
        plt.show()

    def export_data(self, exportDir=None, filename="reflectance_data", file_format="csv"):
        """
        Export the normalized reflectance data for all angles to a single CSV or Excel file.

        Parameters:
        exportDir (str): The directory where the file will be saved.
        filename (str): The name of the file to save (without extension). Default is 'reflectance_data'.
        file_format (str): The format to save the file in. Options are 'csv' or 'excel'. Default is 'csv'.
        """
        if exportDir is None:
            exportDir = os.path.join(self.fileDir, 'exported_data')

        if not os.path.exists(exportDir):
            os.makedirs(exportDir)

        combined_data = None
        for angle, data in self.reflectance_dict.items():
            df = pd.DataFrame(data, columns=['Wavelength (nm)', f'Reflectance at {angle} deg (%)'])
            if combined_data is None:
                combined_data = df
            else:
                combined_data = pd.merge(combined_data, df, on='Wavelength (nm)', how='outer')

        filepath = os.path.join(exportDir, f"{filename}_{self.identifier}.{file_format}")

        if file_format == "csv":
            combined_data.to_csv(filepath, index=False)
        elif file_format == "excel":
            combined_data.to_excel(filepath, index=False)

        print(f"All data saved to {filepath}")

    def normalise_raw(self, region=(1500, 1600)):
        '''Normalised the raw data to the region of interest, using the a global minimum. '''
        newDict = {key: {} for key in self.files.keys()}

        for key, reflectanceFile in self.files.items():
            for angle, data in reflectanceFile.items():
                # breakpoint()
                mask = (data.data[:, 0] >= region[0]) & (data.data[:, 0] <= region[1])
                min_val = np.min(data.data[:, 1])
                max_val = np.max(data.data[mask, 1])
                data.data[:, 1] = (data.data[:, 1] - min_val) / (max_val - min_val) * 100
                newDict[angle] = data.data

            newDict[key] = newDict
    
        self.angleDict = newDict

    def normalise_reflectance(self, region=(1100, 1200), normalisation_type='min'):
        '''Normalises the reflectance data to the specified region. Options for normalisation_type are 'min' and 'max'. 'max' uses the region for the maximum value, 'min' uses the region for the minimum value.'''

        for angle, data in self.reflectance_dict.items():
            mask = (data[:, 0] >= region[0]) & (data[:, 0] <= region[1])
            if normalisation_type == 'min':
                min_val = np.min(data[mask, 1])
            else:
                min_val = np.min(data[:, 1])
                
            if normalisation_type == 'max':
                max_val = np.max(data[mask, 1])
            else:
                max_val = np.max(data[:, 1])
                
            
            # max_val = np.max(data[mask, 1])
            data[:, 1] = (data[:, 1] - min_val) / (max_val - min_val) * 100

        return self.reflectance_dict
    
    def normalise_reflectance_partial(self, region=(1100, 1200), normalisation_type='min'):
        '''Normalises the reflectance data using the region as a mask for either max or minimum values. By selecting a region of interest in the spectrum which is not expected to show angle dependent intensities, angle dependent intensities elsewhere represented more clearly. Note this is in lieu of an absolute or relative intensity reference.'''

        for angle, data in self.reflectance_dict.items():
            mask = (data[:, 0] >= region[0]) & (data[:, 0] <= region[1])
            if normalisation_type == 'min':
                min_val = np.min(data[mask, 1])
                data[:, 1] = data[:, 1] - min_val
                
            elif normalisation_type == 'max':
                max_val = np.max(data[mask, 1])
                data[:, 1] = data[:, 1] / max_val * 100
                

        return self.reflectance_dict

    def truncate_data(self, region=(900, 1650)):
        '''Truncates the data to the specified region'''
        for angle, data in self.reflectance_dict.items():
            mask = (data[:, 0] >= region[0]) & (data[:, 0] <= region[1])
            self.reflectance_dict[angle] = data[mask]

        return self.reflectance_dict
    

if __name__ == '__main__':
    # utility_test()
    # breakpoint()
    # fileDir = r'C:\Users\sjbrooke\OneDrive - The University of Melbourne\Data\Nitu_ITO_04092024'
    # fileDir = r'C:\Users\sjbrooke\OneDrive - The University of Melbourne\Data\Nitu_Ann\ITO_4-10-24' # ITO_3nm-1
    # fileDir = r'C:\Users\sjbrooke\OneDrive - The University of Melbourne\Data\Nitu_Ann\ITO_3nm-2' # ITO_3nm-2
    # fileDir = r'C:\Users\sjbrooke\OneDrive - The University of Melbourne\Data\Nitu_Ann\ITO-3nm-3-Spol' # ITO_3nm-1-Spol
    fileDir = r'C:\Users\sjbrooke\OneDrive - The University of Melbourne\Data\Nitu_Ann\Nitu 22-10-24\P-pol'
    
    # rename_files(fileDir)
    angleData = AngleReflectance(fileDir)
    angleData.identifier = 'ITO-thick-P-pol'# for the export file
    # angleData.plot_original()
    angleData.normalise_raw(region=(1500, 1600))
    # angleData.plot_raw(offset=0)
    angleData.calculate_reflectivity(reference_identifier='reference', sample_identifier='sample', time_normalised=True)
    angleData.truncate_data(region=(900, 1650))
    # angleData.normalise_reflectance(region=(1500, 1600), normalisation_type='max')
    # angleData.normalise_reflectance_partial(region=(1500, 1600), normalisation_type='max')
    # angleData.plot_reflectance(xregion=(900, 1650),  yregion=(-5, 105), save_plot=False)
    angleData.plot_reflectance_individual(xregion=(900, 1650), save_plot=True)
    # angleData.export_data()
