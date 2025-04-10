import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import sys
from skimage import io
from glob import glob
from tkinter import Tk
from tkinter.filedialog import askopenfilename

import matplotlib
matplotlib.rcParams.update({'errorbar.capsize': 4})
from dynamic_roi_draw import run_roi_selector

ROOT_DIR = r'G:\My Drive\Ba Tagging'
FILTER_PATH = ROOT_DIR +r'\code\imag_analisis\filter_stats.csv'
REFERENCE_DIR = ROOT_DIR + r'\spectra\reference_spectra/'

filtAv = pd.read_csv(FILTER_PATH).central_lambda[:10]
filtUn = pd.read_csv(FILTER_PATH).range_width[:10]
filtQE = pd.read_csv(FILTER_PATH).mean_qe[:10]

def get_power(path):
    """Get the exposure time from the settings file.
    Args: path: string with the path to the directory with the settings file.
    Returns: texp: float with the exposure time.
    """
    file_settings = path + '/settings.json'
    df_settings = pd.read_csv(file_settings, sep=':', names=['setting', 'value'], index_col='setting')
    power = float(df_settings.loc['POWER(uW)'].values[0])
    print(f'P = {power} µW')
    return power

def process_counts(arr_counts, filter_df, power):
    """Process the counts from the images."""
    arr_counts = np.array(arr_counts).ravel()
    arr_counts /= filter_df.mean_qe[:10]
    arr_counts /= power   # Divide by the QE and the power
    arr_counts /= (filter_df.range_width[:10]*2)  # Divide by the uncertainty in the transmission
    return arr_counts

def add_roi_info(filter_df, roi, imroi_size):
    """Add ROI information to the filter DataFrame."""
    filter_df.loc['roi_x', 'central_lambda'] = roi[0] + (roi[1] - roi[0]) / 2
    filter_df.loc['roi_y', 'central_lambda'] = roi[2] + (roi[3] - roi[2]) / 2
    filter_df.loc['roi_x', 'range_width'] = roi[1] - roi[0]
    filter_df.loc['roi_y', 'range_width'] = roi[3] - roi[2]
    filter_df.loc['roi_x', 'range_low'] = roi[0]
    filter_df.loc['roi_y', 'range_low'] = roi[2]
    filter_df.loc['roi_x', 'range_high'] = roi[1]
    filter_df.loc['roi_y', 'range_high'] = roi[3]
    filter_df.loc['roi_x', 'sum_counts'] = imroi_size
    filter_df.loc['roi_y', 'sum_counts'] = imroi_size
    return filter_df

def get_spectra(path, roi):
    """Plot the power ramp data for the specified path."""
    files = sorted(glob(path + '\*.tif'))
    power = get_power(path)
    nfilt = len(files)

    for f in files:
        if 'Center-NA' in f:
            f0 = f
        elif 'Dark_Blind' in f:
            fdark = f
    img0 = io.imread(f0).astype(np.int64)
    img_dark = io.imread(fdark).astype(np.int64)
    img_dark = img_dark[roi[0]:roi[1], roi[2]:roi[3]]
    # name = os.path.split(f0)[-1]

    filtstats_path = r'G:\My Drive\Ba Tagging\code\imag_analisis\filter_stats.csv'
    filter_df = pd.read_csv(filtstats_path, index_col=0)

    avg_counts = []
    std_counts = []
    sum_counts = []
    for i in range(nfilt - 2):
        img0 = io.imread(files[i]).astype(np.int64)

        imroi = img0[roi[0]:roi[1], roi[2]:roi[3]]
        imroi -= img_dark
        avg_counts.append(imroi.mean())
        sum_counts.append(imroi.sum())
        std_counts.append(imroi.std() / np.sqrt(imroi.size))

    avg_counts = process_counts(avg_counts, filter_df, power)
    std_counts = process_counts(std_counts, filter_df, power)
    sum_counts = process_counts(sum_counts, filter_df, power)

    filter_df['avg_counts'] = avg_counts
    filter_df['std_counts'] = std_counts
    filter_df['sum_counts'] = sum_counts

    filter_df = add_roi_info(filter_df, roi, imroi.size)

    return filter_df    

def plot_reference_spectrum(name, max_counts_spectrum, ax=None):
    if ax is None:
        ax = plt.gca()
    file = REFERENCE_DIR + name + '.csv'
    df_ref = pd.read_csv(file, names=['wv', 'counts'], skiprows=1, index_col='wv')
    df_ref.counts = df_ref.counts * max_counts_spectrum / df_ref.counts.max()
    ax.plot(df_ref, '-', label=name)
    ax.set(xlabel='Wavelength (nm)', ylabel='Counts')

def analyse_roi(path):
    """Analyse the spectrum of the images in the given path
    """
    root = Tk()
    root.withdraw()  # Hide the main window
    image_path = askopenfilename(title="Select an Image File")
    root.destroy()
    if not image_path:
        print("No image selected. Exiting.")
        return
    img0 = io.imread(image_path).astype(np.int64)

    roi = run_roi_selector(img0)
    
    print('ROI:', roi)

    subdirs = [x[0] for x in os.walk(path)][1:]
    fig, ax = plt.subplots()
    cmax = 0
    print('subdirs:')
    for n, d in enumerate(subdirs):
        print(n + 1, d)
        df = get_spectra(d, roi)
        # print(df)

        ax.errorbar(df['central_lambda'], df['avg_counts'], xerr=df['range_width'], yerr=df['std_counts'], fmt='-o', label=d.split('\\')[-1])
        cmax = max(cmax, np.max(df['avg_counts']))
        df.to_csv(d + '/spectrum_data.csv')

    if 'Rhodamine' in d:
        plot_reference_spectrum('Rhodamine_B', cmax, ax=ax)

    ax.set(xlabel='Wavelength (nm)', ylabel='Counts/ROI/nm/$\mu$W',)
    ax.legend()
    plt.show()
    fig.savefig(path + '/roi_spectrum.png')

if __name__ == '__main__':
    path = sys.argv[1]
    analyse_roi(path)