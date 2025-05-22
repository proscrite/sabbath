import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from scipy.optimize import curve_fit
import os
import sys
from skimage import io
from glob import glob
import json
from tkinter import Tk
from tkinter.filedialog import askopenfilename

import matplotlib
matplotlib.rcParams.update({'errorbar.capsize': 4})
# from dynamic_roi_draw import run_roi_selector



ROOT_DIR = r'G:\My Drive\Ba Tagging'
ROOT_DIR = '/Users/pabloherrero/Library/CloudStorage/GoogleDrive-qmlab@mail.huji.ac.il/My Drive/Ba Tagging'
FILTER_PATH = ROOT_DIR +r'/code/imag_analisis/filter_stats.csv'
REFERENCE_DIR = ROOT_DIR + r'/spectra/reference_spectra/'


def exp_func2(x, a, b, c, d, e):
    return a * np.exp(-x / b) + c * np.exp(-x / d) + e

def get_exposure_time(path):
    """Get the exposure time from the settings file.
    Args: path: string with the path to the directory with the settings file.
    Returns: texp: float with the exposure time.
    """
    file_settings = path + '/settings.json'
    df_settings = pd.read_csv(file_settings, sep=':', names=['setting', 'value'], index_col='setting')

    texp = float(df_settings.loc['EXPOSURE_TIME'].values[0])
    return texp

def get_power(path_file):
    """Get the exposure time from the settings file.
    Args: path: string with the path to the directory with the settings file.
    Returns: texp: float with the exposure time.
    """
    string_power = path_file.split('/')[-1].split('_')[-1]
    power_uW = float(string_power[:-6])

    return power_uW

def plot_roi(img, roi, color='red'):
    # imroi = img[roi[0]:roi[1], roi[4]:roi[3]]
    ax = plt.gca()
    ax.imshow(img)
    ax.add_patch(patches.Rectangle((roi[2], roi[0]), roi[3]-roi[2], roi[1]-roi[0], fill=False, 
                                   edgecolor=color, linewidth=2 ))

def calculate_trajectories(files, roi):
    """Calculate the average intensity of the images in a list of files.
    Args: files: list of strings with the paths to the images.
          mask: 2D numpy array with the binary mask of the field of view.
          roi_size: integer with the number of pixels in the field of view.
    Returns: avg_ints: 1D numpy array with the average intensity values.
    """

    avg_counts = []
    std_counts = []
    sum_counts = []
    results_df = pd.DataFrame()
    for n, f in enumerate(files):
        # try:
        namefile = f.split('\\')[-1]
        print(f"Processing file {n+1}/{len(files)}: {namefile}")
        img = io.imread(f).astype(np.int64)
        # # except ValueError or tifffile.tifffile.TiffFileError or KeyError:
        #     print(f"Error reading file {f}. Skipping...")
        #     continue
        img = img[roi[0]:roi[1], roi[2]:roi[3]]

        img_size = img.shape[0] * img.shape[1]
        sum_img = img.sum()
        mean_img = sum_img / img_size
        std_img = img.std() / np.sqrt(img.size)

        avg_counts.append(mean_img)
        std_counts.append(std_img)
        sum_counts.append(sum_img)

    results_df['avg_counts'] = avg_counts
    results_df['std_counts'] = std_counts
    results_df['sum_counts'] = sum_counts

    return results_df

def fit_plot_trajectories(results_roi, color = None, label = None, ax = None):
    bs = results_roi['avg_counts'].iloc[-1]
    max_val = results_roi['avg_counts'].max()


    time_array = results_roi['time'].values
    try:
        par2, _ = curve_fit(exp_func2, time_array, results_roi['avg_counts'],  p0=(max_val, 7.23, 0.1*max_val, 0.775, bs), bounds=([80, 0, 0, 0, 0], [np.inf, np.inf, np.inf, np.inf, np.inf]))
        results_roi['fit_exp'] = exp_func2(results_roi['time'], *par2)
    except RuntimeError:
        print("Error: curve_fit failed to converge.")
        par2 = [0, 0, 0, 0, 0]

    if ax == None: ax = plt.gca()
    if label == None: label='Rhodamine B 50 µM'

    line = ax.errorbar(time_array, results_roi['avg_counts'], 
             yerr=results_roi['std_counts'], 
             zorder = 1,
             fmt='.', color=color, label=label)[0]

    color = line.get_color()
    try:
        ax.plot(time_array, results_roi['fit_exp'], '-', color=color, lw=2, zorder = 3,
             label=f'{par2[0]:.3f} exp(-t/ {par2[1]:.3f}) + {par2[2]:.3f} exp(-t/ {par2[3]:.3f}) + {par2[4]:.0f}')
    except KeyError:
        pass
    ax.legend()
    ax.set(xlabel='time (min)', ylabel='Avg. counts', title='Fluorescence trajectories')
    return results_roi, par2

def get_fit_roi_info(roi):
    """Add ROI information to the filter DataFrame."""
    filter_df = pd.DataFrame(index=['roi_x', 'roi_y'], columns=['px_range', 'first_px', 'last_px', 'central_px',])
    filter_df.loc['roi_x', 'px_range'] = roi[1] - roi[0]
    filter_df.loc['roi_y', 'px_range'] = roi[3] - roi[2]
    filter_df.loc['roi_x', 'first_px'] = roi[0]
    filter_df.loc['roi_y', 'first_px'] = roi[2]
    filter_df.loc['roi_x', 'last_px'] = roi[1]
    filter_df.loc['roi_y', 'last_px'] = roi[3]
    filter_df.loc['roi_x', 'central_px'] = roi[0] + (roi[1] - roi[0]) / 2
    filter_df.loc['roi_y', 'central_px'] = roi[2] + (roi[3] - roi[2]) / 2
    return filter_df

def export_roi_fit_info(path, roi, par2):
    fit_pars = {'a': par2[0], 't1': par2[1], 'b': par2[2], 't2': par2[3], 'I0': par2[4],}
    roi_df = get_fit_roi_info(roi)
    fit_roi_dict = {'fit_pars': fit_pars, 'roi_df': roi_df}
    # Convert DataFrame to dictionary for JSON serialization
    fit_roi_dict['roi_df'] = fit_roi_dict['roi_df'].to_dict()


    # Export to JSON file
    output_path = path + '/fit_roi_info.json'
    with open(output_path, 'w') as json_file:
        json.dump(fit_roi_dict, json_file, indent=4)

    print(f"Exported fit_roi_info to {output_path}")


def trajectory_roi(path_experiment):
    """Calculate the average intensity of the images in a list of files.
    Args: path_experiment: string with the path to the directory with the images.
    Returns: avg_ints: 1D numpy array with the average intensity values.
    """
    
    sample_name = path_experiment.split('\\')[-2]
    print(f'Calculating trajectories for {sample_name}...')
    files = sorted(glob(path_experiment + '/*.tif'))

    time_array_min = np.arange(len(files)) * get_exposure_time(path_experiment) / 60
    roi = [750, 1500, 500, 1250]

    results_roi = calculate_trajectories(files, roi)
    results_roi['time'] = time_array_min
    results_roi, par2 = fit_plot_trajectories(results_roi, color = 'b', label = sample_name, ax = None)

    results_roi.to_csv(path_experiment + '/results_roi.csv', index=False)
    print(f"Exported results_roi to {path_experiment}/results_roi.csv")
    export_roi_fit_info(path_experiment, roi, par2)



if __name__ == '__main__':
    path_experiment = sys.argv[1]
    trajectory_roi(path_experiment)