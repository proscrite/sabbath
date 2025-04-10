import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import sys
from skimage import io
from glob import glob
import matplotlib
matplotlib.rcParams.update({'errorbar.capsize': 4})
from image_processing import find_fov

# filtAv = [438, 472, 500, 527, 549, 561, 568, 605, 631, 661, 692]     # Until 06-03-2024
# filtUn = np.array([28, 35, 29, 22, 21, 21, 26, 22, 28, 26, 47]) / 2
# filtAv = [438, 472, 549, 575, 586, 605, 631, 661, 676, 692]          # Until 10-03-2025
# filtUn = np.array([28, 35, 21, 35, 26, 22, 28, 26, 29, 47]) / 2
filtAv = [438, 500, 527, 549, 575, 605, 631, 661, 676, 692]          # From 10-03-2025
filtUn = np.array([28, 29, 22, 21, 35, 22, 28, 26, 29, 47]) / 2
filtQE = np.array([0.52654585, 0.61510198, 0.67157561, 0.70026282, 0.71884383, 0.72505143, 0.7279477, 0.72530424, 0.71414267, 0.68976776, 0.6438945])
roi = [750, 1350, 400, 1000]
N = 400

ROOT_DIR = 'G:\\My Drive\\Ba Tagging\\'
FILTER_PATH = ROOT_DIR +'\\code\\imag_analisis\\filter_stats.csv'
filtAv = pd.read_csv(FILTER_PATH).central_lambda[:10]
filtUn = pd.read_csv(FILTER_PATH).range_width[:10]
filtQE = pd.read_csv(FILTER_PATH).mean_qe[:10]

def get_exposure_time(path):
    """Get the exposure time from the settings file.
    Args: path: string with the path to the directory with the settings file.
    Returns: texp: float with the exposure time.
    """
    file_settings = path + '\\settings.json'
    df_settings = pd.read_csv(file_settings, sep=':', names=['setting', 'value'], index_col='setting')

    texp = float(df_settings.loc['EXPOSURE_TIME'].values[0])
    return texp

def remove_outliers(avg_counts, x_time):
    """Remove the outliers from the average counts and the time array.
    Args: avg_counts: 1D numpy array with the average counts.
          x_time: 1D numpy array with the time values.
    Returns: avg_count_out: 1D numpy array with the average counts without outliers.
             x_time_out: 1D numpy array with the time values without outliers.
    """
    cutlow = np.average(avg_counts) - 3*np.std(avg_counts)
    cuthigh = np.average(avg_counts) + 3*np.std(avg_counts)

    avg_count_low = avg_counts[avg_counts > cutlow]
    x_time_low = x_time[avg_counts > cutlow]
    avg_count_out = avg_count_low[avg_count_low < cuthigh]
    x_time_out = x_time_low[avg_count_low < cuthigh]
    return avg_count_out, x_time_out

def calculate_trajectories(files, mask, roi_size):
    """Calculate the average intensity of the images in a list of files.
    Args: files: list of strings with the paths to the images.
          mask: 2D numpy array with the binary mask of the field of view.
          roi_size: integer with the number of pixels in the field of view.
    Returns: avg_ints: 1D numpy array with the average intensity values.
    """
    avg_ints = []

    for f in files:
        img = io.imread(f).astype(np.int64)
        img[~mask] = 0
        avg_int = img.sum() / roi_size
        avg_ints.append(avg_int)

        # quant90.append(np.quantile(img, 0.9))
        # sums.append(np.sum(img))

    avg_ints = np.array(avg_ints)
    return avg_ints

def analyse_trajectories(path, Nexp = None):
    """Plot and save the average intensity trajectories of the images in a directory.
    Args: path: string with the path to the directory with the images.
          Nexp: integer with the number of the experiment to analyze.
    """

    subdirs = [x[0] for x in os.walk(path)][1:]
    colors = ['b', 'orange', 'g', 'r', 'c', 'm', 'y', 'k', 'w']
    print('subdirs:', subdirs)
    fig_outliers, ax_outliers = plt.subplots()
    fig, ax = plt.subplots()

    if Nexp == None:
        for n,d in enumerate(subdirs):
            print(f'Analysing directory {n+1}: {d}')
            texp = get_exposure_time(d)

            files = sorted(glob(d+'\\*.tif'))

            img0 = io.imread(files[0]).astype(np.int64)
            name = os.path.split(files[0])[-1]
            print('Finding FOV on first image: ', name)
            mask_disk= find_fov(img0, name, method='yen', flag_plot=True)    # Refined FOV search
            img0[~mask_disk] = 0
            roi_size = len(img0[mask_disk].ravel())

            av_evol = calculate_trajectories(files, mask = mask_disk, roi_size=roi_size)

            nframes = len(av_evol)
            x_time = np.linspace(0, round(nframes * texp, 1), nframes)
            ax_outliers.plot(x_time, av_evol, 'o', label='Experiment '+str(n+1))
            ax_outliers.set(xlabel='t (s)', ylabel='counts/px (arb. units)', title='Temporal evolution with outliers')
            
            av_evol, x_time = remove_outliers(av_evol, x_time)
            ax.plot(x_time, av_evol, 'o', label='Experiment '+str(n+1))
        ax.set(xlabel='t (s)', ylabel='counts/px (arb. units)', title='Temporal evolution, outliers removed')

        ax_outliers.legend()
        ax.legend()
        plt.show()
        fig.savefig(path+'\\av_trajectories.png')
    
    else:
        d = subdirs[Nexp-1]
        print(f'Analysing directory: {d}')
        texp = get_exposure_time(d)

        files = sorted(glob(d+'\\*.tif'))
        name = os.path.split(files[0])[-1]
        img0 = io.imread(files[0]).astype(np.int64)

        mask_disk= find_fov(img0, name, method='yen', flag_plot=True)    # Refined FOV search
        img0[~mask_disk] = 0
        roi_size = len(img0[mask_disk].ravel())

        av_evol = calculate_trajectories(files, mask = mask_disk, roi_size=roi_size)
        nframes = len(av_evol)
        x_time = np.linspace(0, round(nframes * texp, 1), nframes)
        plt.plot(x_time, av_evol, 'o', color=colors[Nexp-1], label='Experiment '+str(Nexp))
        plt.gca().set(xlabel='t (s)', ylabel='counts/px (arb. units)', title='Temporal evolution with outliers')
        plt.legend()
        plt.show()
        
        av_evol, x_time = remove_outliers(av_evol, x_time)
        fig = plt.figure()

        plt.plot(x_time, av_evol, 'o', label='Experiment '+str(n+1))
        plt.gca().set(xlabel='t (s)', ylabel='counts/px (arb. units)', title='Temporal evolution, outliers removed')
        plt.show()
        fig.savefig(path+'\\av_trajectory_%i.png' %Nexp)

if __name__ == '__main__':
    path = sys.argv[1]
    if len(sys.argv) > 2:
        Nexp = int(sys.argv[2])
    else: Nexp = None
    analyse_trajectories(path, Nexp)

