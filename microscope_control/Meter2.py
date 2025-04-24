import time

from microscope_control.powerm import TLPMX
import ctypes
from ctypes import cdll,c_long, c_ulong, c_uint32,byref,create_string_buffer,c_bool,c_char_p,c_int,c_int16,c_double, sizeof, c_voidp
from microscope_control.powerm.TLPMX import TLPM_DEFAULT_CHANNEL

from microscope_control.Constants import *

wavelength = c_double(515.0)


class Meter:
    def __init__(self):
        self.meter = False
        self.avg_time = ctypes.c_double()
        self.wavelength = ctypes.c_double()

    def __del__(self):
        if bool(self):
            self.close()

    def __bool__(self):
        if self.meter is False:
            return False
        return True

    def open(self, avg=AVG_TIME):
        if bool(self):
            print('power meter already open')
            return True
        
        deviceCount = ctypes.c_uint32()
        meter = TLPMX.TLPMX()

        try:
            meter.findRsrc(ctypes.byref(deviceCount))
        except:
            print('No power meter detected')
            return False
        if deviceCount.value < 1:
            print('No power meter detected')
            return False
        resourceName = ctypes.create_string_buffer(1024)
        meter.getRsrcName(ctypes.c_int(0), resourceName)
        if meter.open(resourceName, ctypes.c_bool(True), ctypes.c_bool(True)) != 0:
            print('Failed connecting to power meter')
            return False
        
        self.meter = meter
        # time.sleep(1)

        meter.setWavelength(wavelength,TLPM_DEFAULT_CHANNEL)

        # Enable auto-range mode.
        # 0 -> auto-range disabled
        # 1 -> auto-range enabled
        meter.setPowerAutoRange(c_int16(1),TLPM_DEFAULT_CHANNEL)

        # Set power unit to Watt.
        # 0 -> Watt
        # 1 -> dBm
        meter.setPowerUnit(c_int16(0),TLPM_DEFAULT_CHANNEL)

        # self.meter.setTimeoutValue(ctypes.c_int32((avg+1)*1000))  # set the timeout to be longer then the averaging time
        # time.sleep(1)  # needs to add sleep for changing parameters except for this one

        # self.meter.getAvgTime(ctypes.c_int16(0), ctypes.byref(self.avg_time))
        # self.meter.setAvgTime(ctypes.c_double(avg))
        # time.sleep(1)

        # self.meter.getWavelength(ctypes.c_int16(0), ctypes.byref(self.wavelength))
        # self.meter.setWavelength(ctypes.c_double(LASER_WAVELENGTH))
        # time.sleep(1)

        return True

    def close(self):
        if bool(self):
            # self.meter.setAvgTime(self.avg_time)
            # time.sleep(1)
            # self.meter.setWavelength(self.wavelength)
            # time.sleep(1)
            self.meter.close()
            self.meter = False

    def read(self):
        if bool(self) is False:
            #print('no active power meter')
            return None
        # Take power measurements and return value
        power = ctypes.c_double()
        self.meter.measPower(ctypes.byref(power), TLPM_DEFAULT_CHANNEL)
        return power.value

