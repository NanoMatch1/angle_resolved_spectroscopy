import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import json
import re

def generate_scan_list(dataDir, params):
    if len(params) != 3:
        print("Please provide the correct number of parameters.")
        return False
    for x in params:
        try:
            float(x)
        except ValueError:
            print("Please provide valid angles.")
            return False
        
    ref_angles = np.arange(float(params[0]), float(params[1]) + float(params[2]), float(params[2]))
    # sample_angles = np.arange(float(params[0]), float(params[1]) + float(params[2]), float(params[2]))


    scan_params = [[angle, angle] for angle in ref_angles]
    scan_list = {'reference': scan_params, 'sample': scan_params}
    with open(os.path.join(dataDir, 'scan_list.json'), 'w') as file:
        json.dump(scan_list, file)
    print("Scan list generated.")
    return True


def rename_files(dataDir, ref_id='reference', sample_id='sample'):
    '''Renames files in the directory based on the scan_list.dat file.'''

    def exclude_files(file_list):
        '''Excludes files which already have the angles in the filename, indicating renaming has been successful.'''

        new_file_list = [x for x in file_list]

        for file in file_list:
            try:
                basename = re.sub(r'\.\w{3}$', '', file)
                endstring = basename.split('_')[-1]
                angles = endstring.split(',')
                if len(angles) > 1:
                    new_file_list.remove(file)
            except Exception as e:
                pass

        
        return new_file_list

    reference_files = [file for file in os.listdir(dataDir) if ref_id in file]
    sample_files = [file for file in os.listdir(dataDir) if sample_id in file]

    reference_files = exclude_files(reference_files)
    sample_files = exclude_files(sample_files)

    
    
    if len(reference_files) == 0 and len(sample_files) == 0:
        print("Files appear to be renamed. Skipping renaming.")
        return

    try:
        sorted_reference_files = sorted(reference_files, key=lambda x: int(x.split('_')[2].split('.')[0]))
        sorted_sample_files = sorted(sample_files, key=lambda x: int(x.split('_')[2].split('.')[0]))
    except ValueError:
        try:
            test_file = reference_files[0].split('_')[2].split('.')[0].split(',')
            test = [float(angle) for angle in test_file]
            print("Files appear to be renamed. Skipping renaming.")
            return
        except Exception as e:
            print(f"Error in file renaming: {e}\nPlease check the files and try again.")
            
    # open json file for scan list
    if not os.path.exists(os.path.join(dataDir, 'scan_list.json')):
        while True:
            user_in = input("Scan list json file not found. Would you like to generate the scan list flie? (y/n): ")
            if user_in.lower() == 'y':
                while True:
                    param_in = input("Enter scan params separated by comma: start_angle,stop_angle,resolution:\n")
                    params = param_in.split(',')
                    if generate_scan_list(dataDir, params) is True:
                        break
                    else:
                        continue

    with open(os.path.join(dataDir, 'scan_list.json'), 'r') as file:
        scan_list = json.load(file)
    
    # breakpoint()
    reference_angles = scan_list.get('reference')
    sample_angles = scan_list.get('sample')

    # breakpoint()

    for idx in range(len(reference_angles)):
        ref_angle = [str(angle) for angle in reference_angles[idx]]
        ref_angle_tag = ','.join(ref_angle)
        ref_rename = sorted_reference_files[idx].split('_')
        ref_rename = '_'.join(ref_rename[:-1]) + f"_{ref_angle_tag}.txt"

        sample_angle = [str(angle) for angle in sample_angles[idx]]
        sample_angle_tag = ','.join(sample_angle)
        sample_rename = sorted_sample_files[idx].split('_')
        sample_rename = '_'.join(sample_rename[:-1]) + f"_{sample_angle_tag}.txt"


        try:
            os.rename(os.path.join(dataDir, sorted_reference_files[idx]), os.path.join(dataDir, ref_rename))
        except Exception as e:
            print(f"Error renaming file: {e}")
        try:
            os.rename(os.path.join(dataDir, sorted_sample_files[idx]), os.path.join(dataDir, sample_rename))
        except Exception as e:
            print(f"Error renaming file: {e}")
    print("Files renamed.")

class ReflectionFile:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.data_type, self.angles = self._parse_filename(self.filename)
        self.header = {}
        self.data = None
        self.load_file()

    def __repr__(self):
        return f"ReflectionFile: {self.data_type}:{self.angles}:{self.filename}"
    
    def __str__(self):
        return f"{self.data_type}: {self.angles}"
    
    def info(self):
        return {'data_type': self.data_type, 'angles': self.angles, 'filename': self.filename}

    def _parse_filename(self, filename):
        '''Parses the filename to extract the data type and angles. File convention needs to contain:
        1. A data type identifier ("ref" or sample identifier (not yet implimented)
        2. Angles in the format "a,b" where a and b are the two angles in degrees.'''

        def match_angles(name_string):
            pattern = r"-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?"
            matches = re.findall(pattern, name_string) 
            return matches
        
        def match_basename_identifier(pattern, name_string):
            match = re.match(pattern, name_string.lower())
            return match

        def extract_angles(name_string):
            angles = match_angles(filename)
            if len(angles) > 1:
                print(f"Multiple angle matches found for {filename}. Using the first one.")
            angles = angles[0].split(',')
            angles = tuple([float(angle) for angle in angles])
            return angles

        # generate basename and identifier
        name_parts = filename.split('_')
        file_basename = name_parts[0]

        reference_matches = match_basename_identifier(r'.*ref.*', file_basename)
        # sample_name_matches = match_basename_identifier(file_basename, r'.*.*')

        if reference_matches:
            data_type = 'reference'
        else:
            data_type = 'sample'
            print(f"predicting sample for {file_basename}")

        angles = extract_angles(filename)

        return data_type, angles

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

    def __init__(self, fileDir, reference_axis=(1, 1)):
        '''Initialise the class and load files from the directory as angle resolved reflectance data. 
        
        reference_axis can be a combination of integer values, spanning the range of the total number of axes. It provides a mapping of axis for which uncoupled scans are to be normalised. The ordering is (sample, reference). Secondary axes are selected by default. For instance, (0, 0) maps the two primary axes together, such that all of the samples with angles (a, _) will be normalised agains the reference with (a, _). (0, 1) maps (a, _) to (_, a), and (1, 1) maps (_, a) to (_, a).
        
        Use caution when selecting axes - you must consider an appropriate logical reference mapping for your data to be quantitative.'''

        self.fileDir = fileDir
        self.dataDict = self.load_data()
        self.data_ok = self.report_info()

        self.sample_identifier = 'sample'
        self.reference_identifier = 'reference'
        self.reference_axis = reference_axis
        self.identifier = None
        self.warning_flags = []

    def load_data(self):
        files = [os.path.join(self.fileDir, file) for file in os.listdir(self.fileDir) if file.endswith('.txt')]
        reflection_files = [ReflectionFile(file) for file in files]

        angle_dict = {}
        for file in reflection_files:
            if file.data_type not in angle_dict:
                angle_dict[file.data_type] = {}
            angle_dict[file.data_type][file.angles] = file

        return angle_dict
    
    def report_info(self):
        references = {}
        samples = {}

        for file_type, file_dict in self.dataDict.items():
            # print(f"{file_type}:")
            for angles, file in file_dict.items():
                infoDict = file.info()
                if file_type == 'reference':
                    references[angles] = infoDict
                else:
                    samples[angles] = infoDict

        print("### Report ###")
        if len(references) != len(samples):
            print("Warning: Different number of reference and sample files.")

        ref_angles_set = set(references.keys())
        sample_angles_set = set(samples.keys())

        missing_in_samples = ref_angles_set - sample_angles_set
        missing_in_references = sample_angles_set - ref_angles_set

        if missing_in_samples:
            print(f"Warning: The following reference angles are missing in samples: {missing_in_samples}")
        elif missing_in_references:
            print(f"Warning: The following sample angles are missing in references: {missing_in_references}")
        else:
            print("All angles accounted for.")

        return True

    
    def find_reference(self, angles:tuple):
        '''Finds the reference file based on the reference axis mapping'''
        sample_angle = angles[self.reference_axis[0]]

        reference_candidates = [angle for angle in self.dataDict['reference'].keys() if angle[self.reference_axis[1]] == sample_angle]

        assert len(reference_candidates) > 0 , f"No reference found for {angles}."
        if len(reference_candidates) > 1:
            self.warning_flags.append(f"Multiple references found for {angles}. Using the first one.")

        return reference_candidates[0]
    


    def calculate_reflectivity(self, reference_identifier=None, sample_identifier=None, time_normalised=False):
        '''Calculates the reflectivity of the sample using the reference data. If time_normalised is True, the reflectance is normalised by the integration time of the sample.'''

        if reference_identifier is None:
            reference_identifier = self.reference_identifier
        if sample_identifier is None:
            sample_identifier = self.sample_identifier
        
        reference_dict = self.dataDict[reference_identifier]
        sample_dict = self.dataDict[sample_identifier]
        self.reflectance_dict = {}

        for angles in sample_dict:
            sample_file = sample_dict.get(angles)
            reference_file = reference_dict.get(angles)
            # breakpoint()
            if reference_file is None:
                reference_file = reference_dict.get(self.find_reference(angles))
            
            sample_data = sample_file.data
            reference_data = reference_file.data
            reflectance_data = sample_data[:, 1] / reference_data[:, 1]

            if time_normalised is True:
                # Handle different integration times if needed
                integration_time_ratio = sample_file.integration_time / reference_file.integration_time
                reflectance_data *= integration_time_ratio

            reflectance_data *= 100  # Convert to percentage
            # reflectance_data /= 2 # the data is doubled for some reason, possibly normalisation time #TODO: Fix this Its from the integration time of 0.5s... but the ratios should be the same...
            self.reflectance_dict[angles] = np.column_stack((sample_data[:, 0], reflectance_data))

        return self.reflectance_dict

    def plot_raw(self, offset=0):
        label_1, label_2 = list(self.dataDict.keys())[:2]
        key_dict_1 = self.dataDict[label_1]
        key_dict_2 = self.dataDict[label_2]

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
                if not os.path.exists(exportDir):
                    os.makedirs(exportDir)
            plt.savefig(os.path.join(exportDir, f"{self.identifier}_individual.png"))
        plt.show()


    def plot_original(self):
        data_dict = self.dataDict['sample']
        ref_dict = self.dataDict['reference']

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
        newDict = {key: {} for key in self.dataDict.keys()}

        for key, reflectanceFile in self.dataDict.items():
            for angles, data in reflectanceFile.items():
                mask = (data.data[:, 0] >= region[0]) & (data.data[:, 0] <= region[1])
                if True not in mask:
                    print("Mask region empty. Skipping normalisation")
                    return
                min_val = np.min(data.data[:, 1])
                max_val = np.max(data.data[mask, 1])
                data.data[:, 1] = (data.data[:, 1] - min_val) / (max_val - min_val) * 100
                newDict[angles] = data.data

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
    fileDir = r'C:\Users\sjbrooke\OneDrive - The University of Melbourne\Data\Nitu_ITO_04092024'
    fileDir = r'C:\Users\sjbrooke\OneDrive - The University of Melbourne\Data\Shifan'
    # fileDir = r'C:\Users\sjbrooke\OneDrive - The University of Melbourne\Data\Nitu_Ann\ITO_4-10-24' # ITO_3nm-1
    # fileDir = r'C:\Users\sjbrooke\OneDrive - The University of Melbourne\Data\Nitu_Ann\ITO_3nm-2' # ITO_3nm-2
    # fileDir = r'C:\Users\sjbrooke\OneDrive - The University of Melbourne\Data\Nitu_Ann\ITO-3nm-3-Spol' # ITO_3nm-1-Spol
    # fileDir = r'C:\Users\sjbrooke\OneDrive - The University of Melbourne\Data\Nitu_Ann\Nitu 22-10-24\P-pol'
    # fileDir = r'C:\Users\sjbrooke\OneDrive - The University of Melbourne\Data\Aurora\DNF'
    
    ref_id = 'reference'
    sample_id = '20uL'

    rename_files(fileDir, ref_id=ref_id, sample_id=sample_id)
    angleData = AngleReflectance(fileDir, reference_axis=(1, 1))
    angleData.identifier = '20uL-unpol'# for the export file
    angleData.plot_original()
    # angleData.normalise_raw(region=(1500, 1600))
    # angleData.plot_raw(offset=0)
    angleData.calculate_reflectivity(reference_identifier=ref_id, sample_identifier=sample_id, time_normalised=True)
    angleData.truncate_data(region=(440, 1000))
    breakpoint()
    # angleData.normalise_reflectance(region=(1500, 1600), normalisation_type='max')
    # angleData.normalise_reflectance_partial(region=(1500, 1600), normalisation_type='max')
    angleData.plot_reflectance(xregion=(440, 1000),  yregion=(-5, 105), save_plot=False)
    angleData.plot_reflectance_individual(xregion=(440, 1000), save_plot=True)
    angleData.export_data()
