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
filtQE = np.array([0.52654585, 0.61510198, 0.67157561, 0.70026282, 0.71884383, 0.72505143, 0.72530424, 0.71414267, 0.68976776, 0.6438945])   # Inaccurate, actual transmission values are around 0.9

ROOT_DIR = r'G:\My Drive\Ba Tagging'
FILTER_PATH = ROOT_DIR +r'\code\imag_analisis\filter_stats.csv'
REFERENCE_DIR = ROOT_DIR + r'\spectra\reference_spectra/'

filtAv = pd.read_csv(FILTER_PATH).central_lambda[:10]
filtUn = pd.read_csv(FILTER_PATH).range_width[:10]
filtQE = pd.read_csv(FILTER_PATH).mean_qe[:10]

def plot_reference_spectrum(name, max_counts_spectrum, ax=None):
    if ax is None:
        ax = plt.gca()
    file = REFERENCE_DIR + name + '.csv'
    df_ref = pd.read_csv(file, names=['wv', 'counts'], skiprows=1, index_col='wv')
    df_ref.counts = df_ref.counts * max_counts_spectrum / df_ref.counts.max()
    ax.plot(df_ref, '-', label=name)
    ax.set(xlabel='Wavelength (nm)', ylabel='Counts')

def prepare_spectrum(files, roi=None):
    """Prepare the spectrum of the images in the given list of files
    Args: files: list of strings with the paths to the images.
          roi: list of integers with the coordinates of the region of interest.
    Returns: cntQe: 1D numpy array with the counts per QE."""
    
    nfilt = len(files)

    for f in files:
        if 'Center-NA' in f:
            f0 = f
        elif 'Dark_Blind' in f:
            fdark = f
    img0 = io.imread(f0).astype(np.int64)
    name = os.path.split(f0)[-1]
    print('Finding FOV on image with No Filters: ', name)

    if method == 'None':
        method = 'yen'
    binary_mask = fov_threshold(img, method)
    
    binary_mask = morphology.remove_small_objects(binary_mask, min_size=10)  # Remove small noise
    mask_disk = find_fov(img0, name, method='yen', flag_plot=True)  # Refined FOV search

    img0[~mask_disk] = 0
    imsize = mask_disk[mask_disk].shape  # Number of pixels in the circular mask

    if roi is not None:
        imroi = img0[roi[0]:roi[1], roi[2]:roi[3]]
        imsize = imroi.shape[0] * imroi.shape[1]
    offset = 100 * imsize

    img_dark = io.imread(fdark).astype(np.int64)

    avInt = []
    unInt = []
    for i in range(nfilt - 2):
        print('Processing file: ', os.path.split(files[i])[-1])
        img = io.imread(files[i]).astype(np.int64)
        img -= img_dark
        img[~mask_disk] = 0

        if roi is not None:
            img = img[roi[0]:roi[1], roi[2]:roi[3]]

        intPx = (img.sum()) / imsize
        avInt.append(intPx)

        unPx = np.sqrt((img ** 2).sum()) / imsize
        unInt.append(unPx)

    avInt = np.array(avInt)
    unInt = np.array(unInt)
    cntQe = avInt / filtQE
# cntQe /= (filtUn*2)

    unInt /= filtQE
# unInt /= (filtUn*2)
    return cntQe, unInt

def analyse_spectrum(path):
    """Analyse the spectrum of the images in the given path
    """
    roi = [0, 2048, 0, 2048]
    # roi = [400, 1300, 400, 1300]

    subdirs = [x[0] for x in os.walk(path)][1:]
    fig, ax = plt.subplots()
    cmax = 0
    print('subdirs:')
    for n, d in enumerate(subdirs):
        print(n + 1, d)
        files = sorted(glob(d + '/*.tif'))
        # print(files)
        c, un = prepare_spectrum(files, roi)

        ax.errorbar(x=filtAv, xerr=filtUn, y=c / (filtUn * 2), yerr=un / (filtUn * 2), fmt='o-', label=n + 1)
        cmax = max(cmax, np.max(c / (filtUn * 2)))
    
    if 'Rhodamine' in d:
        plot_reference_spectrum('Rhodamine_B', cmax, ax=ax)

    ax.axvline(x=550, color='k', linestyle='--', alpha=0.5, label='DM-cutoff')
    ax.axvline(x=515, color='red', linestyle='--', alpha=0.5, label='Laser')


    ax.set(xlabel='$\lambda$ (nm)', ylabel='cnts/px/$\lambda$')
    ax.legend()
    plt.show()
    fig.savefig(path + '/quick_spectrum.png')

if __name__ == '__main__':
    path = sys.argv[1]
    analyse_spectrum(path)