import cv2
import time
import os
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from ast import literal_eval
import serial
import sys
from skimage import io
import warnings
warnings.filterwarnings("ignore", message=".*low contrast image.*")
import logging
logging.getLogger('numba').setLevel(logging.INFO)
# sys.path.append(r'C:\Users\owner\Documents\thorlabs_apt-master')
sys.path.append(r'G:\My Drive\Ba Tagging')
sys.path.append(r'G:\My Drive\Ba Tagging\code\imag_analisis')
from microscope_control.Constants import *
import microscope_control.Wheel as Wheel
import microscope_control.Meter2 as Meter2   # Meter2 for TLPMX (new API version), Meter for TLMP (older version)
import microscope_control.saving as saving
from microscope_control import SetupSettings
import microscope_control.motor as motor
from .utils import *

from .pylablib_DCAM.devices.DCAM import DCAMCamera
from pylablib.devices.Thorlabs import KinesisMotor
# import thorlabs_apt as apt
# from quick_spectra import analyse_spectrum
# from get_trajectories import analyse_trajectories
# from analyse_power_ramps import analyse_ramp
from imag_analysis.dynamic_roi_draw import run_roi_selector


data_struct = np.dtype([('date', 'double'), ('power', 'double'), ('name', str), ('images', (np.uint16, (24, 2048, 2048)))])

global texp

class Setup:
    def __init__(self):
        # self.cam = Camera.Camera()
        self.cam = DCAMCamera(idx=0)
        self.wheel = Wheel.Wheel()
        self.meter = Meter2.Meter()
        self.settings = pd.DataFrame()
        # self.motor = apt.Motor(26002227)
        self.motor = KinesisMotor("26002227", scale=2184533.33) # scale is in mm/step
        self.arduino = serial.Serial("COM6", 9600, timeout=1) # Open serial port to arduino
        
        self.fraction_power = 1.0  # Fraction of maximum power attenuated by the ND filter wheel
        self.power_correction_factor = 10.0    # Factor to compensate for the losses in the beam splitter
        self.max_power = self.get_power()
        self.position_max = 0.0
        self.shutter_status = False
        self.texp = 0.5
        self.roi = [0, 2048, 0, 2048]  # Default ROI for the whole image
        self.open_all_devices()
        self.filter_id = self.wheel.get_filter()

        self.cam.set_exposure(self.texp)   # Set default exposure time to 0.5s
        self.cam.set_readout_speed('fast')   # Set default readout speed to fast
        self.cam.set_attribute_value('binning', 1)  # Set default binning to 1
        
        self.menu = \
            {
            'i': (self.take_spectra, 'Take Spectra'),
            'f': (self.image_filter, 'Take image of single filter'),
            'F': (self.select_filter, 'Move filter wheel'),
            'a': (self.autofocus, 'Autofocus'),
            'h': (0, 'List of commands'),
            'z': (self.get_zpos, 'Move Z position'),
            'l': (self.live_cam, 'Live camera'),
            's': (self.toggle_shutter, 'Shutter (open/close)'),
            't': (self.take_sequence, 'Take time evolution'),
            'e': (self.get_exposure, 'Set camera exposure'),
            'v': (self.get_readout_speed, 'Get readout speed'),
            'p': (self.print_power, 'Get power reading'),
            'n': (self.attenuate_power, 'Set power attenuation'),
            'N': (self.set_maximum_power, 'Set power to maximum'),
            'r': (self.power_ramp, 'Power ramps'),
            'R': (self.select_ROI, 'Select ROI'),
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

    def take_single_frame(self, name, path, filters, shutter = True):
        # print('Filters: ', filters)
        self.wheel.set_filter(filters)
        # self.cam.exposure_time(self.cam.exposure)
        # print('Camera exposure: ', round(self.cam.get_exposure(), 2) )
        if shutter:
            self.open_shutter()
        
        data = self.cam.snap(timeout=15)
    
        if shutter:
            self.close_shutter()

        # num = saving.save_npy(data, name)
        try:
            power = round(self.meter.read() * 1e6, 4)
        except: 
            power = None        
            print('Cannot read power')
        saving.single_tif_save(data, path, name, power, filters)
        return data

    def live_cam(self):
        if self.cam.is_opened() is True:
            self.cam.close()
            time.sleep(2)
        import live_cam
        
        live_cam.dcam_live_capturing()
        print('Returned from live_cam')
        del(live_cam)
        
        self.cam.open()
        self.cam.set_exposure(self.texp)
        # th = threading.Thread(target=live_cam.dcamtest_thread_live)

    def take_images(self, name, filters):
        if filters != 0:
            rootpath = IMAGE_SINGLE_SAVE_LOCATION
            path = saving.check_path_save(rootpath, name, filters=None)
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
            powers = []
            for i in range(11, -1, -1):
                self.wheel.set_filter(i+1)
                print("Current filter: %i" %(i+1))
                # self.cam.exposure_time(self.cam.exposure)
                # print('Current exposure is %0.2f s \n' %(self.cam.exposure) )
                
            #    camera.exposure_time(FILTERS_EXPOSER[i + 1])
                self.open_shutter()
                data_set['images'][0][i] = self.cam.snap(timeout=15)
                powers.append(round(self.get_power() * 1e6, 4))
                self.close_shutter()
            
            save_path = saving.save_tif_set(data_set['images'][0], name, data_set['power'][0])
            mean_power = np.mean(powers)
            
            self.settings = SetupSettings.add_settings_value(self.settings, 'POWER(uW)', mean_power)
            print('In take images, settings: ', self.settings)

            SetupSettings.write_settings(save_path, self.settings)
            print_image_set(data_set['images'][0])
            return save_path

    def select_ROI(self):
        self.open_shutter()
        img0 = self.cam.snap(timeout=15)
        self.close_shutter()
        self.roi = run_roi_selector(img0)

    def send_ttl(self, command):
        self.arduino.write(command.encode())  # Send 'H' or 'L'
        response = self.arduino.readline().decode().strip()
        # print("Arduino says:", response)

    def toggle_shutter(self):
        self.send_ttl('T')
        self.shutter_status = not self.shutter_status

    def open_shutter(self):
        self.send_ttl('H')
        self.shutter_status = True
    
    def close_shutter(self):
        self.send_ttl('L') 
        self.shutter_status = False

    def get_raw_power(self):
        if self.meter.open(1):
            current_power = round(self.meter.read(), 7)   # Need high precision for low power reading
        self.meter.close()
        return current_power
     
    def get_power(self):
        """Get the current power reading from the meter"""
        current_power = self.get_raw_power()
        current_power = current_power * self.power_correction_factor
        return current_power

    def select_filter(self):
        filter_id = 0
        while filter_id == 0:
            filter_id = get_filters_to_snap()
        self.move_filter(filter_id)
    
    def move_filter(self, filter_id):
        """Move filter wheel to the selected filter"""
        self.wheel.set_filter(filter_id)
        self.filter_id = filter_id

    def print_power(self):
        if self.meter.open(1):
            current_power = self.meter.read()
            print(f'Power: {current_power*1e6} μW')
            time.sleep(2)
        self.meter.close()
        return current_power

    def get_attenuation_factor(self):
        """Prompt user for the attenuation factor (CLI user input)"""
        new_fraction_power = input('Enter the power fraction (0 to 1) \nor order of magnitude (-1 to -4): ')
        try:
            new_fraction_power = float(new_fraction_power)
        except ValueError:
            print("Invalid input. Please enter a number between 0 and 1")
        """Set the power to a percentage of the maximum power"""
        if new_fraction_power > 1.0:
            raise ValueError("Percentage must be between 0 and 1")
        self.fraction_power = new_fraction_power
        self.attenuate_power(new_fraction_power)

    def attenuate_power(self, new_fraction_power):
        """Attenuate the power to a fraction of the maximum power, according to exponential decay
           Parameters:
               new_fraction_power (float): The new fraction of power to set (0 to 1)
        """

        exp_parameter = 0.01685    # Exponential decay parameter for the power ramp (conversion factor from desired power to angle)
        if new_fraction_power > self.fraction_power:
            # Attenuate power to a fraction of the maximum power, according to exponential decay
            theta = -np.log(new_fraction_power - self.fraction_power) / exp_parameter
            self.fraction_power = new_fraction_power
            print('Theta: ', theta)
        elif (new_fraction_power > 0.0) and (new_fraction_power <= 1.0):
            # Attenuate power to a fraction of the maximum power, according to exponential decay"""
            theta = -np.log(new_fraction_power) / exp_parameter
            self.fraction_power = new_fraction_power
            print('Theta: ', theta)
        
        elif (new_fraction_power < 0.0) and (new_fraction_power > -5.0):
            # Attenuate power to the order of magnitude of the maximum power
            self.fraction_power = np.exp(new_fraction_power)
            theta = new_fraction_power / exp_parameter
            print('Theta: ', theta)

        needed_steps = 1600 * theta / 360
        # difference = self.fraction_power * 1600 - needed_steps    # Absolute scale: store previous fraction power and adjust the steps to meet the new fraction power
        # steps = int(difference) # 1600 steps for 100% power
        print(f'Fraction power: {self.fraction_power}, new fraction power: {new_fraction_power}')
        # print(f'Needed steps: {steps}, difference: {difference}, steps: {steps}')
        print(f'Needed steps: {needed_steps}')

        command = f'{needed_steps}\n'  # Format the command as 'XXX'
        self.arduino.write(command.encode())  # Send command to Arduino
        # response = self.arduino.readline().decode().strip()
        # print("Arduino says:", response)
        time.sleep(3)
 
        current_power = self.get_power()
        print(f'Power: {current_power*1e6} μW')
        self.fraction_power = new_fraction_power
        # self.check_overflow()

    def check_overflow(self):
        """Check for overflow conditions and handle them"""
        current_power = self.get_power()
        if current_power > self.max_power:
            input(f"Found power: {current_power*1e6} μW, setting to maximum power. Press any key to continue")
            self.fraction_power = 1.0
            self.position_max = 0.0
            self.max_power = current_power
            self.settings = SetupSettings.add_settings_value(self.settings, 'POWER(uW)', current_power*1e6)

    def set_maximum_power(self):
        """Set the power to maximum"""
        steps = np.linspace(0, 1600, 10)
        powers = []
        angles = []
        self.send_ttl('H')
        time.sleep(2)
        for i, s in enumerate(steps):
            command = f'{int(steps[1])}\n'    # Fixed step, pass to arduino as int
            # print(f'Command: {command}')
            self.arduino.write(command.encode())  # Send command to Arduino
            time.sleep(2) 
            power = self.get_power()
            powers.append(power)
            # print(f'Step: {i}, position: {s}, Power: {round(power * 1e6, 4)} uW')
            angle = round(360 * s / 1600, 2)
            angles.append(angle)
            print(f'Angle: {angle}, Power: {round(power * 1e6, 2)} uW')

        # df = pd.DataFrame({'angle': angles, 'power': powers})
        # df.to_csv('power_ramp.csv', index=False)
        
        position_max = np.argmax(powers)
        print(f'Max power at position: {position_max}, steps: {steps[position_max]}', )
        print(f'Moving to position: {steps[position_max] - 1600}')
        self.fraction_power = 1.0
        self.position_max = steps[position_max]
        self.max_power = powers[position_max]
        self.settings = SetupSettings.add_settings_value(self.settings, 'POWER(uW)', powers[position_max]*1e6)
        command = f'{steps[position_max] - 1600}\n'
        self.arduino.write(command.encode())  # Send command to Arduino
        response = self.arduino.readline().decode().strip()
        print("Arduino says:", response)
        time.sleep(1)
        # self.send_ttl('L')

    def power_ramp(self):
        """Power ramp"""
        name = get_sample_name()
        while True:
            filters = get_filters_to_snap()
            if filters != 0:
                break
        npoints = get_nframes()
        texp = self.cam.get_exposure()

        question = 'Sample:\t' + name + '\nFilter:\t' + FILTERS[filters] 
        question += 'Exposure:\t' + str(texp) + 's' 
        question += '\nNumber of points:\t %i \n' %npoints
        question += '\nTake image with this parameters? y/n\n'
        if get_yes_no(question):
            self.wheel.set_filter(filters)
            rootpath = IMAGE_POWER_SAVE_LOCATION
            path = saving.check_path_save(rootpath, name, filters=filters)
            self.open_shutter()
            self.meter.open(1)
            time.sleep(1)
            steps = np.linspace(0, 1600, npoints)
            first_power = round(self.meter.read(), 7)
            self.take_single_frame(name, path, filters, shutter=False) # Get initial image before attenuating
            powers = [first_power * 1e6]   # Get initial power
            angles = [0]

            # Iterate over steps up to last one (repeated unattenuated power)
            for i, s in enumerate(steps[:-1]):
                command = f'{int(steps[1])}\n'
                angles.append(round(s * 360 / 1600, 1))
                self.arduino.write(command.encode())  # Send command to Arduino
                time.sleep(3)
                power = round(self.meter.read(), 7)   # Need high precision for low power reading
                powers.append(power*1e6)
                print(f"Frame nr. {i}, Power: {round(power * 1e6, 2)} uW")
                self.settings = SetupSettings.add_settings_value(self.settings, 'POWER(uW)', power*1e6)
                data = self.cam.snap(timeout=15)
                saving.single_tif_save(data, path, name, round(power * 1e6, 2), filters)
        
        else:
            return
        
        self.arduino.write(command.encode())   # Advance one more step (without taking image) to recover the unattenuated power

        self.meter.close()
        self.close_shutter()
        SetupSettings.write_settings(path, self.settings)
       
        df_power = pd.DataFrame({'angle': angles, 'power(uW)': powers})   # Record power and angle and store in csv file
        df_power.to_csv(path + '\power_ramp.csv', index=False)         
        path_sample = os.path.split(path)[0] + '/'
        print('Calling analyse_ramp for path: ', path_sample)
        
        analyse_ramp(path_sample, roi=self.roi)

    def open_cam(self):
        self.cam.open()
        self.cam.set_exposure(self.texp)
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
        self.arduino.close()


    def autofocus(self):
        self.open_shutter()
        self.motor.main_autofocus(self.cam, self.motor, self.wheel)
        self.close_shutter()

    def take_spectra(self):
        name = get_sample_name()
        filters = 0
        
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

            self.settings = SetupSettings.add_settings_value(self.settings, 'EXPOSURE_TIME', texp)
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
            path = saving.check_path_save(rootpath, name, filters=filters)
            # mean_intensities = []
            self.open_shutter()

            # plt.ion()
            # fig, ax = plt.subplots()
            # line, = ax.plot([], [], 'b-o')  # Initialize an empty line plot
            # ax.set_xlabel('Frame number')
            # ax.set_ylabel('Mean intensity')

            for i in range(nframes):
                print("Frame nr. %i" %i)
                img = self.take_single_frame(name, path, filters, shutter=False)
                img = img[self.roi[0]: self.roi[1], self.roi[2]: self.roi[3]]
                # mean_intensities.append(np.mean(img))
                # line.set_data(range(len(mean_intensities)), mean_intensities)
                # ax.relim()              # Recompute the data limits
                # ax.autoscale_view()     # Rescale the view to the new data
                # plt.draw()              # Update the plot with new data
            
            self.close_shutter()
            # plt.ioff()
            # plt.show()

            SetupSettings.write_settings(path, self.settings)
            path_sample = os.path.split(path)[0] + '/'    # Get path to sample folder, this way the spectrum analysis is done for all measurements in the same folder
            print('Calling analyse_spectrum for path: ', path_sample) 
            # analyse_trajectories(path_sample)

            # self.close_all_devices()
            
    def take_sequence(self):
        if self.open_all_devices() is False:
            return
        name = get_sample_name()
        filters = get_filters_to_snap()
        nframes = get_nframes()
        texp = self.cam.get_exposure()
        question = 'Sample:\t' + name + '\nFilter:\t' + FILTERS[filters] + '\n'
        question += 'Exposure:\t' + str(texp) + 's' 
        question += '\nNumber of frames:\t %i \n' %nframes
        question += '\nTake image with this parameters? y/n\n'
        if not get_yes_no(question):
            return
        rootpath = IMAGE_TIMERUN_SAVE_LOCATION
        path = saving.check_path_save(rootpath, name, filters)
        # mean_intensities = []
        self.open_shutter()
        print('Devices open, taking sequence')
        data = self.cam.grab(nframes)
        print('Sequence taken, data shape: ', len(data))
        power = round(self.meter.read() * 1e6, 4)
        self.close_shutter()

        # Save sequence in individual files
        for n, img in enumerate(data):
            print("Saving Frame nr. %i" %n)
            # img = img[self.roi[0]: self.roi[1], self.roi[2]: self.roi[3]]
            path_file = path + '\\' + FILTERS[filters] + '_' + '_P_' + str(power) + 'uW_frame_' + str(n).zfill(3) +'.tif'

            io.imsave(path_file, img)
            # saving.single_tif_save(img, path, name, power, filters)
        SetupSettings.write_settings(path, self.settings)

    def get_exposure(self):
        current_exposure = self.cam.get_exposure()
        key = check_expTime(current_exposure)
        if key == 'q':
            return
        else:
            self.texp = key
            self.set_exposure(self.texp)

    def set_exposure(self, texp):
        self.cam.set_exposure(texp)
        self.texp = texp
        self.settings = SetupSettings.add_settings_value(self.settings, 'EXPOSURE_TIME', texp)
        print('Exposure time set to %0.2f s' %texp)

    def get_readout_speed(self):
        """Prompt user for readout speed"""
        ro_speed = self.cam.get_readout_speed()
        print('Readout speed: ', ro_speed)

        """Set readout speed"""
        speed_dict = {'1': 'slow', '2': 'fast'}
        ro_speed_key = input(f'Enter readout speed: {speed_dict}\n')
        if ro_speed_key not in speed_dict.keys():
            print('Invalid readout speed, setting to fast')
            ro_speed = 'fast'
        else:
            ro_speed = speed_dict[ro_speed_key]
            self.set_readout_speed(ro_speed)

    def set_readout_speed(self, ro_speed):
        """Set readout speed (slow or fast)"""
        self.cam.set_readout_speed(ro_speed)
        self.settings = SetupSettings.add_settings_value(self.settings, 'READOUT_SPEED', ro_speed)

    def get_binning(self):
        """Prompt user for binning"""
        current_binning = self.cam.get_attribute_value('binning')
        print('Current binning: ', current_binning)

        binning_dict = {'1': 1, '2': 2, '4': 4}
        bin_key = input(f'Enter readout speed: {binning_dict}\n')
        if bin_key not in binning_dict.keys():
            print('Invalid readout speed, setting to fast')
            sel_binning = 1
        else:
            sel_binning = binning_dict[bin_key]
            self.set_binning(sel_binning)

    def set_binning(self, sel_binning):
        """Set readout speed (slow or fast)"""
        self.cam.set_attribute_value('binning', sel_binning)
        self.settings = SetupSettings.add_settings_value(self.settings, 'BINNING', sel_binning)

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
        z_pos = round(self.motor.get_position(), 3)
        print("Current Z position: ", z_pos)
        return z_pos
    
    def get_zpos(self):
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
            self.move_zpos(new_zpos)

    def move_zpos(self, new_zpos=None):
        """Move Z position to new value"""
        self.motor.move_to(new_zpos)
        self.motor.wait_move()
        print('New Z position: ', round(self.motor.get_position(), 3))
        self.settings = SetupSettings.add_settings_value(self.settings, 'ZPOS(mm)', new_zpos)
        
    def move_zpos_step(self, step=None):
        """Move Z position to new value"""
        self.motor.move_by(step)
        self.motor.wait_move()
        print('New Z position: ', round(self.motor.get_position(), 3))
        self.settings = SetupSettings.add_settings_value(self.settings, 'ZPOS(mm)', self.motor.get_position())

    def init_settings(self):
        fin = SetupSettings.find_recent_settings()
        print('Loading recent settings at :', fin)
        self.settings = SetupSettings.read_settings(fin)

        if self.motor is not None:
            z_pos = self.read_zpos()
            self.settings = SetupSettings.add_settings_value(self.settings, 'ZPOS(mm)', z_pos)

        texp = self.cam.get_exposure()
        self.settings = SetupSettings.add_settings_value(self.settings, 'EXPOSURE_TIME', texp)

        print('Last sample name: ', self.settings.loc['SAMPLE_NAME', 'value'])

    def settings_menu(self):
        self.settings = SetupSettings.edit_settings(self.settings)


def main():
    st = Setup()
    # st.open_all_devices()
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


