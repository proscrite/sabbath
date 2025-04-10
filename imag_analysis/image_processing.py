import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

import os
import sys
from skimage import io, color, filters, morphology, measure, exposure
from skimage.draw import disk

from skimage.filters import threshold_otsu, threshold_li, threshold_yen

ROOT_DIR = 'G:\\My Drive\\Ba Tagging\\'
FILTER_PATH = ROOT_DIR +'\\code\\imag_analisis\\filter_stats.csv'
filtQE = pd.read_csv(FILTER_PATH).mean_qe

def fov_threshold(img, method = ['otsu', 'li', 'yen']):
    threshold = {'otsu': threshold_otsu, 'li': threshold_li, 'yen': threshold_yen}
    img = exposure.equalize_hist(img)
    threshold = threshold[method](img)
    print('Threshold: '+method, threshold)
    binary_mask = img > threshold

    return binary_mask

def make_circular_region(binary_mask):
    """Finding the field of view in a gray image. This will be the disk with the largest area and solidity.
    Args: gray_image: 2D numpy array representing the gray image.
    Returns: fov_mask: 2D numpy array representing the binary mask of the field of view.
    
    """
    # Perform morphological closing to fill small gaps
    binary_mask = morphology.closing(binary_mask, morphology.disk(10))

    # Label connected components
    labeled_mask = measure.label(binary_mask)

    # Measure properties of labeled regions
    regions = measure.regionprops(labeled_mask)

    # Find the largest circular region based on area and solidity
    best_region = None
    best_circularity = 0
    best_area = 100             # Initialize area over 100 to ignore small noise
    for region in regions:
        area = region.area
        perimeter = region.perimeter if region.perimeter > 0 else 1
        circularity = 4 * np.pi * (area / (perimeter ** 2))
        
        if circularity > best_circularity and area > best_area:  # Find the largest circular region
            best_circularity = circularity
            best_region = region
            best_area = area

    # Create a mask for the detected FOV
    fov_mask = np.zeros_like(binary_mask, dtype=bool)

    if best_region:
        fov_mask[labeled_mask == best_region.label] = True
    return fov_mask, best_area, best_region

def find_fov(img, name: str, method = ['None', 'otsu', 'li', 'yen'], flag_plot = True):
    """Full FOV detection in a gray image.
    Args: gray_image: 2D numpy array representing the gray image.
    Returns: fov_mask: 2D numpy array representing the binary mask of the field of view.
    
    """
    
    if method == 'None':
        method = 'yen'
    binary_mask = fov_threshold(img, method)
    
    binary_mask = morphology.remove_small_objects(binary_mask, min_size=10)  # Remove small noise
    fov_mask, area, region = make_circular_region(binary_mask)   # Find the most circular region in the mask, this is the fine grained FOV

    mask_disk = np.zeros_like(img, dtype=bool)
    rr, cc = disk(center=region.centroid, radius=region.axis_major_length/2, shape=mask_disk.shape)   # Make a perfect circular mask
    mask_disk[rr, cc] = True

    if flag_plot:
        fig_fov, ax_fov = plt.subplots()
        obj_imshow = ax_fov.imshow(mask_disk * img)
        plt.colorbar(obj_imshow, ax=ax_fov)
        plt.scatter(region.centroid[1], region.centroid[0], color='red')
        ax_fov.add_patch(Circle((region.centroid[1], region.centroid[0]), region.axis_major_length/2, fill=False, color='red'))
        ax_fov.set(title='FOV detection' + name)
        
    return mask_disk


def offset_circular_mask(img, best_region, best_area, flag_plot = True):
    """Create a circular mask based on the detected region.
    args: 
          img: 2D numpy array representing the image.
          best_region: regionprops object representing the detected region.
          best_area: int representing the area of the detected region.
          flag_plot: bool to display the mask.
    returns:
          circular_mask: 2D numpy array representing the circular
            mask centered on the detected region
    """
    # Extract the centroid (regionprops returns (row, col))
    center_y, center_x = best_region.centroid  

    # Use the known or calculated radius, e.g. from area = πr²:
    # radius ≈ sqrt(area / π). If your area is ~2,625,898:
    fixed_radius = int(np.sqrt(best_area / np.pi))

    # Create a coordinate grid
    height, width = img.shape
    Y, X = np.ogrid[:height, :width]

    # Build the circular mask. This will be True inside the circle.
    circular_mask = (X - center_x)**2 + (Y - center_y)**2 <= fixed_radius**2
    # Display the mask
    if flag_plot:
        plt.figure(figsize=(8, 6))
        plt.imshow(circular_mask, cmap='gray')
        plt.title("Offset Circular Mask (Partially Outside Image)")
    return circular_mask



def prepare_spectrum(files, roi = None):
    nfilt = len(files)
    
    img0 = io.imread(files[0]).astype(np.int64)
    mask_disk= find_fov(img0, method='yen', flag_plot=False)    # Refined FOV search
    
    # circ_mask = offset_circular_mask(img, best_region, best_area, flag_plot=False)  # Rough (perfect) circular mask
    img0[~mask_disk] = 0
    imsize = mask_disk[mask_disk].shape    # Number of pixels in the circular mask
    # imsize = img0.shape[0] * img0.shape[1]
    
    if roi != None:
        imroi = img0[roi[0]:roi[1], roi[2]:roi[3]]
        imsize = imroi.shape[0] * imroi.shape[1]
    offset = 100 * imsize

    avInt = []
    unInt = []
    for i in range(nfilt-1):
        img = io.imread(files[i]).astype(np.int64)
        img[~mask_disk] = 0

        if roi != None:
            img = img[roi[0]:roi[1], roi[2]:roi[3]]
        intPx = (img.sum() - offset) / imsize
        avInt.append(intPx)
        
        unPx = np.sqrt((img**2).sum()) / imsize
        unInt.append(unPx)

    avInt = np.array(avInt)
    unInt = np.array(unInt)
    cntQe = avInt / filtQE
    # cntQe /= (filtUn*2)

    unInt /= filtQE
    # unInt /= (filtUn*2)
    return cntQe, unInt