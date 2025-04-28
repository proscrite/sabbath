from microscope_control.Constants import *
from ast import literal_eval
import matplotlib.pyplot as plt
def time_date():
    return time.strftime(TIME_FORMAT)

def tif_file_name(filter_num, use_time=False):
    if use_time:
        return str(filter_num) + "_" + FILTERS[filter_num] + "_" + time_date() + ".tif"
    return str(filter_num) + "_" + FILTERS[filter_num] + ".tif"

def get_yes_no(question):
    while True:
        key = input(question)
        if key == 'y':
            return True
        elif key == 'n':
            return False
        else:
            print('invalid key')

def check_expTime(current_exposure=None):
    question = 'Current exposure is %0.2f s \n' %(current_exposure)
    print(question)
    try:
        while True:
            key = input('Choose exposure time, press any letter to cancel:\n')
            if (key.isnumeric()) and (int(key) == 0):
                return 0.5
            elif (key.isnumeric()):
                'Returning to main'
                return float(key)
            elif type(literal_eval(key)) == float:
                return float(key)
            else:
                print('invalid key')
                return 'q'
    except ValueError or TypeError or NameError as e:
        return 'q'

def get_sample_name():
    while True:
        print_dict(SAMPLES)
        key = input('choose sample:\n')
        if (key.isnumeric()) and (int(key) == 0):
            return input('Write sample name\n')
        elif (key.isnumeric()) and (int(key) in SAMPLES):
            return SAMPLES[int(key)]
        elif (key == 'q'):
            return 'exit'
        else:
            print('invalid key')

def get_filters_to_snap():
    while True:
        print_dict(FILTERS)
        print('0:\tAll filters')
        key = input('choose filter to snap:\n')
        if (key.isnumeric()) and (int(key) == 0):
            return 0
        elif (key.isnumeric()) and (int(key) in FILTERS):
            return int(key)
        else:
            print('invalid key')

def get_nframes():
    while True:
        key = input('choose number of frames (default 400):\n')
        if (key.isnumeric()) and (int(key) == 0):
            return 400
        elif (key.isnumeric()):
            return int(key)
        else:
            print('invalid key')


def print_dict(dict):
    print()
    for i in dict:
        print(str(i) + ':\t' + dict[i])


def print_image_set(image_set):
    fig_12img, ax_12img = plt.subplots(3, 4)
    fig_12img.tight_layout()
    cut = 500

    for row in range(3):
        for col in range(4):
            area = image_set[col + row * 4, cut:2048 - cut, cut:2048 - cut]
            img = ax_12img[row, col].imshow(area)
            title = str(FILTERS_BANDS[col + row * 4 + 1][0]) + '[nm], ' + str(FILTERS_BANDS[col + row * 4 + 1][1]) + '[nm]'
            ax_12img[row, col].set_title(title)
            ax_12img[row, col].axis('off')
            fig_12img.colorbar(img, ax=ax_12img[row, col])
    plt.show()  # block=False
