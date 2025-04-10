import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import sys
from skimage import io
from glob import glob
import matplotlib
matplotlib.rcParams.update({'errorbar.capsize': 4})

def get_power_ramp(path, roi):
    """Plot the power ramp data for the specified path."""
    files = sorted(glob(path+'\*.tif'), reverse=False)
    power_df = pd.read_csv(path + '\power_ramp.csv')
    assert len(power_df) == len(files)
    avg_counts = []
    std_counts = []
    sum_counts = []
    for f in files:
        img0 = io.imread(f).astype(np.int64)
        roi = [1500, 1650, 800, 950]
        # roi = [0, 2048, 0, 2048]
        imroi = img0[roi[0]:roi[1], roi[2]:roi[3]]
        avg_counts.append(imroi.mean())
        sum_counts.append(imroi.sum())
        std_counts.append(imroi.std() / np.sqrt(imroi.size))

    power_df['avg_counts'] = avg_counts
    power_df['std_counts'] = std_counts
    power_df['sum_counts'] = sum_counts
    # power_df['power(uW)'] = sorted(power_df['power(uW)'], reverse=True)
    return power_df    

def analyse_ramp(path0, roi):
    subdirs = sorted(next(os.walk(path0))[1])
    for subdir in subdirs:
        path = os.path.join(path0, subdir)
        power_df = get_power_ramp(path, roi=roi)
        power_df.to_csv(path + '\power_ramp.csv', index=False)
        linear_fit = np.poly1d(np.polyfit(power_df['power(uW)'], power_df['avg_counts'], 1))
        x_fit = np.linspace(0, np.max(power_df['power(uW)']), 100)
        
        lines = plt.errorbar(power_df['power(uW)'], power_df['avg_counts'], yerr=power_df['std_counts'], fmt='o', label=subdir)
        plt.plot(x_fit, linear_fit(x_fit), '-', color = lines[0].get_color())

        plt.gca().set(xlabel='Power (µW)', ylabel='Average Counts/ROI', xscale='log', title='Power ramps ' + path0.split('\\')[-1])
        plt.legend()