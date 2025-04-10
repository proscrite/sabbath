import sys
sys.path.append(r'C:\Users\owner\Documents\thorlabs_apt-master')

import cv2
import time
from PIL import Image
from skimage import exposure, filters

import os
import matplotlib
import numpy as np
import time
from Constants import *
from matplotlib import pyplot as plt
from scipy.stats import kurtosis

from ast import literal_eval
import Camera
from pylablib_DCAM.devices.DCAM import DCAMCamera
import Wheel
import Meter
import saving
#matplotlib.interactive(True)
sys.path.append(r'G:\My Drive\Ba Tagging\code\imag_analisis')

from image_processing import find_fov

# import thorlabs_apt as apt
# apt.list_available_devices()
# motor = apt.Motor(26002227)
# camera = DCAMCamera(idx=0)
# meter = Meter.Meter()
# wheel = Wheel.Wheel()

def get_expTime():
    while True:
        key = input('Choose exposure time (default 0.5):\n')
        if (key.isnumeric()) and (int(key) == 0):
            return 0.5
        elif (key.isnumeric()):
            return key
        elif type(literal_eval(key)) == float:
            return key
        else:
            print('invalid key')

def get_yes_no(question):
    while True:
        key = input(question)
        if key == 'y':
            return True
        elif key == 'n':
            return False
        else:
            print('invalid key')

def single_tif_save(data, path, pos):
    
    path += '\\' + str(pos) + '.tif'
    imax = np.amax(data)
    if imax > 0:
        image_multiplayer = int(65535 / imax)
        data = data * image_multiplayer
    else:
        image_multiplayer = 1

    img = Image.fromarray(data)
    img.save(path)

def test_position(initPos, step):
    motor.move_by(step)
    should = round( initPos+step, 2) 
    actualPos = motor.position

    if abs(actualPos - should) > 0.015:
        print("Insufficient sleep time for init position, homing...")
        motor.move_home(True)
        time.sleep(45)
        exit

def loop_autofocus(camera, motor, step, nsteps, mask, method = ['laplace', 'counts', 'kurt'], flag_plot=False):
    metric = []
    positions = []
    figf, ax = plt.subplots()
    for i in range(nsteps):
        motor.move_by(step, blocking = True)
        # print("Intended Position:", initPos+step*(i))

        print(f"Step: {i+1}/{nsteps}, Pos motor: {round(motor.position, 3)}")
        positions.append(round(motor.position, 4))

        time.sleep(1)
        img = camera.snap(timeout=15)

        img[~mask] = 0
        # img = exposure.equalize_hist(img)
        if method == 'counts':
            metric.append(np.sum(img))
        elif method == 'laplace':
            metric.append(np.sum(filters.laplace(img)**2))
        elif method == 'kurt':
            metric.append( kurtosis(img.flatten(), fisher=True, bias=False ))

        # if flag_plot:   # Update plot at each step
        #     ax.plot(positions, metric, 'o-')
        #     plt.

    if flag_plot:
        ax.plot(positions, metric, 'o-')
        ax.set(xlabel = f'Step ({step} mm)', ylabel= method+' (arb. units)')

    focus_position = positions[np.argmax(metric)]
    return focus_position, metric

def main_autofocus(camera, motor, wheel):

    print("Initialize camera")
    camera.open()
    camera.set_exposure(0.5)
    print("Exposure: ", round(camera.get_exposure(), 1))

    filter_focus = 7
    wheel.open()
    wheel.set_filter(filter_focus)

    # initPos = 16.9
    initPos = motor.position
    motor.move_to(initPos, blocking = True)
    print("Pos motor:", round(motor.position, 3))
    
    # Find fov
    img0 = camera.snap(timeout=15)   
    img0 = exposure.equalize_hist(img0)
    circ_mask = find_fov(img0, name='Find FOV', method='otsu', flag_plot=True)
    img0[~circ_mask] = 0
    plt.show()
    plt.close(plt.clf())

    if get_yes_no('Continue? (y/n) \n'):
        print('Continuing...')
    else:
        print('Exiting...')
        return

    step1 = 0.1
    nsteps1 = 30
    step2 = 0.05

    focus_position, _ = loop_autofocus(camera=camera, motor=motor, step = step2, nsteps=nsteps1, mask = circ_mask, method = 'kurt', flag_plot=True)
    
    print('Focus position is ', focus_position)
    motor.move_to(focus_position, blocking = True)
    img_focus = camera.snap(timeout=15)
        
    fig_focus, ax_focus = plt.subplots()
    show_focus = ax_focus.imshow(img_focus)
    ax_focus.set_title('Focus image')
    fig_focus.colorbar(show_focus)
    plt.show()
    
if __name__ == '__main__':
    main_autofocus(camera, motor, wheel)
