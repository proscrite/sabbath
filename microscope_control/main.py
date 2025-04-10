import cv2
import time
import os
import numpy as np
import pandas as pd
from Constants import *
from matplotlib import pyplot as plt
from ast import literal_eval
from pylablib_DCAM.devices.DCAM import DCAMCamera
import Wheel
import Meter2    # Meter2 for TLPMX (new API version), Meter for TLMP (older version)
import saving
import SetupSettings
import motor
import serial

import sys
import warnings
warnings.filterwarnings("ignore", message=".*low contrast image.*")
sys.path.append(r'C:\Users\owner\Documents\thorlabs_apt-master')
sys.path.append(r'G:\My Drive\Ba Tagging')
sys.path.append(r'G:\My Drive\Ba Tagging\code\imag_analisis')

import thorlabs_apt as apt
from utils import *
from quick_spectra import analyse_spectrum
from get_trajectories import analyse_trajectories

data_struct = np.dtype([('date', 'double'), ('power', 'double'), ('name', str), ('images', (np.uint16, (24, 2048, 2048)))])

global texp

class Setup:
    def __init__(self):
        # self.cam = Camera.Camera()
        self.cam = DCAMCamera(idx=0)
        self.wheel = Wheel.Wheel()
        self.meter = Meter2.Meter()
        self.settings = pd.DataFrame()
        self.motor = apt.Motor(26002227)
        self.cam.set_exposure(0.5)   # Set default exposure time to 0.5s
        
        self.menu = \
            {
            'i': (self.take_spectra, 'Take Spectra'),
            'f': (self.image_filter, 'Take image of single filter'),
            'F': (self.move_filter, 'Move filter wheel'),
            'a': (self.autofocus, 'Autofocus'),
            'h': (0, 'List of commands'),
            'z': (self.move_zpos, 'Move Z position'),
            't': (self.time_evolution, 'Take time evolution'),
            'e': (self.set_exposure, 'Set camera exposure'),
            ',': (self.settings_menu, 'Settings menu'),
            'q': (self.leave, 'quit')
            # 'cam': (self.show_prop_camera, 'Show camera proerties'),
            # 's': (self.set_cam_properties, 'Set camera property'),
            # 's': (self.take_sequence, 'Take sequence'),
        }


    def __del__(self):
        if self:
            self.close_all_devices()

    def print_menu(self, mode):
        if mode == 'main': menu = self.menu
        elif mode == 'set': menu = self.menu_settings
        print()
        for i in menu.keys():
            print(i + ':\t' + menu[i][1])

    def take_single_frame(self, name, path, filters):
        # print('Filters: ', filters)
        self.wheel.set_filter(filters)
        # self.cam.exposure_time(self.cam.exposure)
        # print('Camera exposure: ', round(self.cam.get_exposure(), 2) )
        data = self.cam.snap(timeout=15)
        # num = saving.save_npy(data, name)
        try:
            power = round(self.meter.read() * 1e6, 4)
        except: 
            power = None        
            print('Cannot read power')
        saving.single_tif_save(data, path, name, power, filters)
        return data

    def take_images(self, name, filters):
        if filters != 0:
            rootpath = IMAGE_SINGLE_SAVE_LOCATION
            path = saving.check_path_save(rootpath, name)
            self.take_single_frame(name, path, filters)
            power = round(self.meter.read() * 1e6, 4)
            self.settings = SetupSettings.add_settings_value(self.settings, 'POWER(uW)', power)
            
            SetupSettings.write_settings(path, self.settings)
            return path

        else:
            data_set = np.zeros(1, dtype=data_struct)
            data_set['date'][0] = np.double(time.time())
            data_set['name'][0] = name
            rootpath = IMAGE_SET_SAVE_LOCATION
            # print('Before loop: current exposure is %0.2f s \n' %(self.cam.get_exposure()) )

            for i in range(11, -1, -1):
                self.wheel.set_filter(i+1)
                print("Current filter: %i" %(i+1))
                # self.cam.exposure_time(self.cam.exposure)
                # print('Current exposure is %0.2f s \n' %(self.cam.exposure) )
                
            #    camera.exposure_time(FILTERS_EXPOSER[i + 1])
                data_set['images'][0][i] = self.cam.snap(timeout=15)
            
            save_path = saving.save_tif_set(data_set['images'][0], name, data_set['power'][0])
            power = round(self.meter.read() * 1e6, 4)

            self.settings = SetupSettings.add_settings_value(self.settings, 'POWER(uW)', power)

            SetupSettings.write_settings(save_path, self.settings)
            print_image_set(data_set['images'][0])
            print()

    def move_filter(self):
        filters = 0
        while filters == 0:
            filters = get_filters_to_snap()
        self.wheel.set_filter(filters)

        if self.meter.open(1):
            print(f'Power: {self.meter.read()} W')
            time.sleep(1)
        self.meter.close()

    def open_cam(self):
        self.cam.open()
        self.cam.set_exposure(0.5)
        while True:
            if not self.cam.is_opened():
                if get_yes_no('Camera failed opening. Try again? y/n\n') is False:
                    return False
            else:
                break
        return True
    
    def open_all_devices(self):
        while True:
            if not self.wheel.open():
                if get_yes_no('Filter wheel failed opening. Try again? y/n\n') is False:
                    return False
            else:
                break
        self.meter.open()
        return True

    def close_all_devices(self):
        self.cam.close()
        self.wheel.close()
        self.meter.close()
    def autofocus(self):
        self.open_shutter()
        motor.main_autofocus(self.cam, self.motor, self.wheel)
        self.close_shutter()

    def take_spectra(self):
        name = get_sample_name()
        filters = 0
        texp = 7.0
        self.cam.set_exposure(texp)   # Set exposure to spectra taking value
        self.settings = SetupSettings.add_settings_value(self.settings, 'EXPOSURE_TIME', texp)
    
        question = 'Sample:\t' + name + '\nAll filters\n'
        question += 'Exposure:\t' + str(texp) + 's' 
        question += '\nTake image with this parameters? y/n\n'
        if get_yes_no(question):
            if self.open_all_devices() is False:
                return
            pathsave = self.take_images(name, filters)
            # self.close_all_devices()
            path_sample = os.path.split(pathsave)[0] + '/'    # Get path to sample folder, this way the spectrum analysis is done for all measurements in the same folder
            print('Calling analyse_spectrum for path: ', path_sample) 
            # analyse_spectrum(path_sample)

            self.cam.set_exposure(0.5)   # After saving, reset exposure to default value
            self.settings = SetupSettings.add_settings_value(self.settings, 'EXPOSURE_TIME', 0.5)
        else:
            pass

    def image_filter(self):
        while True:
            name = get_sample_name()
            if name == 'exit': break
            filters = get_filters_to_snap()
            #if filters == 0:
                #dark_image = get_yes_no('Take a dark images at the end? y/n\n')
            if filters == 0:
                question = 'Sample:\t' + name + '\nAll filters\n' #Dark image:\t' + str(dark_image)
            else:
                question = 'Sample:\t' + name + '\nFilter:\t' + FILTERS[filters]
            #question += 'Current exposure is %0.2f s, do you want to change it? (y/n) \n' %(camera.exposure)
            question += '\nTake image with this parameters? y/n\n'
            if get_yes_no(question):
                if self.open_all_devices() is False:
                    return
                self.take_images(name, filters)
                # self.close_all_devices()
            else:
                print('Open all devices failed')
                break
            
    def time_evolution(self):
        name = get_sample_name()
        while True:
            filters = get_filters_to_snap()
            if filters != 0:
                break
        nframes = get_nframes()
        texp = self.cam.get_exposure()
        question = 'Sample:\t' + name + '\nFilter:\t' + FILTERS[filters] 
        question += 'Exposure:\t' + str(texp) + 's' 
        question += '\nNumber of frames:\t %i \n' %nframes
        question += '\nTake image with this parameters? y/n\n'
        if get_yes_no(question):
            rootpath = IMAGE_TIMERUN_SAVE_LOCATION
            path = saving.check_path_save(rootpath, name)
            for i in range(nframes):
                print("Frame nr. %i" %i)
                self.take_single_frame(name, path, filters)
            SetupSettings.write_settings(path, self.settings)
            # self.close_all_devices()
            
    # def take_sequence(self):
    #     if self.open_all_devices() is False:
    #             return
    #     print('Devices open, taking sequence')
    #     data = self.cam.take_sequence()
    #     print(data)
       

    def set_exposure(self):
        if self.cam.is_opened() is False:
            return
        question = 'Current exposure is %0.2f s \n' %(self.cam.get_exposure())
        print(question)
        try:
            texp = float(get_expTime())
            self.cam.set_exposure(texp)
            self.settings = SetupSettings.add_settings_value(self.settings, 'EXPOSURE_TIME', texp)
        except ValueError or TypeError or NameError:
            return
        # self.cam.close()

    def show_prop_camera(self):
        if self.cam.is_opened() is False:
            return
        print(self.cam.get_all_attribute_values() )
        time.sleep(3)
        # self.cam.close()

    def set_cam_properties(self):
        if camera.open() is False:
            return
        camera.get_all_attribute_values()
        camera.close()

    def leave(self, code=0):
        self.close_all_devices()
        exit(code)

    def read_zpos(self):
        """Return z position from motor"""
        z_pos = round(self.motor.position, 3)
        print("Current Z position: ", z_pos)
        return z_pos
    
    def move_zpos(self):
        z_pos = self.read_zpos()
        try:
            new_zpos = input('Current Z position is %0.3f mm, enter to move to new position\n' %z_pos)
            new_zpos = float(new_zpos)
        except ValueError:
            print('Invalid input, please input float number')
            return
        if new_zpos > 25.0:
            print('Z position too high, max value is 21.0 mm')
            return
        else:
            self.motor.move_to(new_zpos, blocking=True)
            print('New Z position: ', round(self.motor.position, 3))
            self.settings = SetupSettings.add_settings_value(self.settings, 'ZPOS(mm)', new_zpos)
        
    
    def init_settings(self):
        fin = SetupSettings.find_recent_settings()
        print('Loading recent settings at :', fin)
        self.settings = SetupSettings.read_settings(fin)

        if self.motor is not None:
            z_pos = self.read_zpos()
            self.settings = SetupSettings.add_settings_value(self.settings, 'ZPOS(mm)', z_pos)

        texp = self.cam.get_exposure()
        self.settings = SetupSettings.add_settings_value(self.settings, 'EXPOSURE_TIME', texp)


    def settings_menu(self):
        self.settings = SetupSettings.edit_settings(self.settings)


def main():
    st = Setup()
    st.open_all_devices()
    st.open_cam()
    st.init_settings()
    # st.camera.open()
    # st.camera.exposure_time(EXPOSURE_TIME)
    while True:
        st.print_menu('main')
        key = input('\nEnter a new command\nenter \'h\' for help\n')
        if key == 'h':
            pass
        elif key in st.menu:
            st.menu[key][0]()
        else:
            print("invalid key")


if __name__ == '__main__':
    main()


