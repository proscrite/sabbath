import time
import os
import numpy as np
from microscope_control.Constants import *
#import cv2
from PIL import Image
from skimage import io
import piexif
import subprocess
import re
import warnings
warnings.filterwarnings("ignore", message=".*low contrast image.*")

def read_exif(filename):
    result = subprocess.run([EXIFTOOL_APP, filename], stdout=subprocess.PIPE)
    _res = result.stdout.decode("utf-8").split("\n")
    res = {}
    for p in _res:
        field = re.split(" +: ", p)
        if len(field) == 2:
            res[field[0]] = field[1]
    return res


def set_exif_field(filename, field, value):
    result = subprocess.run([EXIFTOOL_APP, '-' + str(field) + '="' + str(value) + '" ', filename], stdout=subprocess.PIPE)

    if re.search(EXIFTOOL_OK_STRING, result.stdout.decode('utf-8')):
        return True
    return False


def save_npy(data, name):
    today = time.strftime(TIME_FORMAT_TODAY)
    path = NP_SAVE_LOCATION + today

    if not os.path.exists(path):
        os.makedirs(path)

    path += '\\' + name

    if not os.path.exists(path):
        os.makedirs(path)

    files = os.listdir(path)

    num = -1
    for file in files:
        if file.endswith('.npy'):
            num = max(num, int(file[:-4]))

    num += 1
    file_name = f"{num}.npy"
    path += '\\' + file_name
    np.save(path, data)
    return num


def check_path_save(rootpath, name, filters=None):
    today = time.strftime(TIME_FORMAT_TODAY)
    path = rootpath + today + '\\' + name

    try:
        nsets = sorted(next(os.walk(path))[1])
    except StopIteration:
        if not os.path.exists(path): os.makedirs(path)
        nsets = sorted(next(os.walk(path))[1])

   ####### Check number of existing measurements in directory
    try: 
        last_set = int(nsets[-1])
        print('Number of sets: ', len(nsets))
        print('Nsets: ', nsets)
        print('Last set number: ', nsets[-1])
        print('Last set: ', last_set)
        print('Path: ', path)
    except IndexError: last_set = 0
   ####### Set current measurement as last_set + 1 (previously 'num')
    path += '\\' + str(last_set+1).zfill(2)

   ######  For time and ramp measurements, add the filter number to the path. Ex: /sample/3-f7-575nm/
    if filters is not None:
        path += '-filt' + str(filters) + str(FILTERS[filters].split('_')[0][6:])

    if not os.path.exists(path):
        os.makedirs(path)
    return path


def single_tif_save(data, path, name, power, filters):
    
    # path_file = path + '\\' + FILTERS[filters] + '_' + time.strftime('%H-%M-%S') + '.tif'
    path_file = path + '\\' + FILTERS[filters] + '_' + time.strftime('%H-%M-%S') + '_P_' + str(power) + 'uW.tif'

    imax = np.amax(data)
    # if imax > 0:
    #     image_multiplayer = int(65535 / imax)
    #     data = data * image_multiplayer
    # else:
    #     image_multiplayer = 1

    # img = Image.fromarray(data)
    # img.save(path_file)
    io.imsave(path_file, data)


def save_tif_set(data, name, power):
    rootpath = IMAGE_SET_SAVE_LOCATION
    path = check_path_save(rootpath, name)

    t = time.strftime('_%H-%M-%S')
    for filters in range(len(data)):
        path_file = path + '\\' + str(FILTERS[filters+1]) + t + '.tif'
        print('Filter save: ', filters)
        print(path_file)
        imax = np.amax(data[filters])
        # if imax > 0:
        #     image_multiplayer = int(65535 / imax)
        #     data = data * image_multiplayer
        # else:
        #     image_multiplayer = 1
        io.imsave(path_file, data[filters])
        # img = Image.fromarray(data[filters])
        # img.save(path_file)
        
    return path
        # set_exif_field(path, 'ExposureTime', int(FILTERS_EXPOSER[filters]*1000))) # problem writing into
        # set_exif_field(path_file, 'ImageDescription', name)
        # set_exif_field(path_file, 'DateTimeOriginal', time.localtime())
        # set_exif_field(path_file, 'Artist', AURTHUR)
        # comment = 'Laser power:' + str(power) + ',Value stretch factor:' + str(image_multiplayer) \
        #     + ',Exposure Time:' + str(int(FILTERS_EXPOSER[filters+1]*1000))
        # set_exif_field(path, 'XPComment', comment)

# def save_tiff(data, rootpath, num, name, power, filters=1):
#     print('Saving .tif files.')
#     if num == -1:
#         single_tif_save(data, rootpath, name, power, filters)
#     else:
#         save_tif_set(data, name, power, num)


if __name__ == '__main__':
    a = np.random.random((12, 10, 10))
    save_tiff(a, 1, 'test_sample', 0.000123, 7)
    """
    for i in range(10):
        data = np.random.random((10, 10))
        save_npy(data, 'test1')

    for i in range(10):
        data = np.random.random((10, 10))
        save_npy(data, 'test2')
    """
