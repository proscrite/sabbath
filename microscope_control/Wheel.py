from microscope_control import FWxC_COMMAND_LIB as fwxc
from microscope_control.Constants import *
import time


class Wheel:
    def __init__(self):
        self.wheel = False
        self.location = None

    def __del__(self):
        if self:
            self.close()

    def __bool__(self):
        if self.wheel is False:
            return False
        return True

    def open(self):
        if self:
            # print('wheel already open')
            return True
        device_list = fwxc.FWxCListDevices()
        if len(device_list) <= 0:
            print('There is no devices connected')
            return False

        wheel_serial_number = device_list[0][0]
        self.wheel = fwxc.FWxCOpen(wheel_serial_number, 115200, 3)
        if self.wheel < 0:
            return False
        pos = [0]
        fwxc.FWxCGetPosition(self.wheel, pos)
        self.location = pos[0]
        return True

    def close(self):
        if self:
            fwxc.FWxCClose(self.wheel)
            self.wheel = False

    def set_filter(self, location):
        if self is False:
            print('no wheel connected')
            return
        fwxc.FWxCSetPosition(self.wheel, location)
        if location >= self.location:
            sleep_time = location - self.location
        else:
            sleep_time = 12 - self.location + location
        # time.sleep(sleep_time*0.8)      # arbitrary number that seems to work
        time.sleep(1)
        pos = [0]
        fwxc.FWxCGetPosition(self.wheel, pos)
        self.location = pos[0]
        if self.location != location:
            time.sleep(1)       # arbitrary extra time
            fwxc.FWxCGetPosition(self.wheel, pos)
            self.location = pos[0]
            if self.location != location:
                print('Failed to set filter')
                return False
        return True

    def get_filter(self):
        if self is False:
            print('no wheel connected')
            return
        pos = [0]
        fwxc.FWxCGetPosition(self.wheel, pos)
        self.location = pos[0]
        return self.location

