"""Sample script for showing captured image with dcam.py.

This script recognizes the camera and acquires with dcam.py.
The acquired images are displayed live with OpenCV.

This sample source code just shows how to use DCAM-API.
The performance is not guranteed.
"""

__date__ = '2021-06-18'
__copyright__ = 'Copyright (C) 2021-2024 Hamamatsu Photonics K.K.'
import sys
sys.path.append(r'C:\Users\owner\Documents\Hamamatsu_DCAMSDK4\samples\python')
import cv2
# pip install opencv-python
# Tested Version (Win/Lnx): 4.6.0.66/4.9.0.80
# License: Apache2 Software License (https://github.com/opencv/opencv/blob/master/LICENSE)
# for display image

from dcam import *
# control DCAM functions

def dcamtest_show_framedata(data, windowtitle, windowstatus):
    """Show image data.

    Show numpy buffer as an image with OpenCV function.

    Args:
        data (void): NumPy array.
        windowtitle (char): Window name.
        windowstatus (int): Last window status returned by dcamtest_show_framedata function. Specify 0 when calling the first time.
    
    Returns:
        int: Window status.
    """
    if windowstatus > 0 and cv2.getWindowProperty(windowtitle, cv2.WND_PROP_VISIBLE) == 0:
        return -1
        # Window has been closed.
    if windowstatus < 0:
        return -1
        # Window is already closed.
    
    if data.dtype == np.uint16:
        imax = np.amax(data)
        if imax > 0:
            imul = int(65535 / imax)
            # print('Multiple %s' % imul)
            data = data * imul

        # Resize the image to make the window smaller
        height, width = data.shape
        new_height, new_width = height // 4, width // 4
        resized_data = cv2.resize(data, (new_width, new_height))

        # Apply colormap
        colormap_data = cv2.applyColorMap(cv2.convertScaleAbs(resized_data, alpha=255.0/65535), cv2.COLORMAP_HOT)

        cv2.imshow(windowtitle, colormap_data)
        return 1
    else:
        print('-NG: dcamtest_show_image(data) only support Numpy.uint16 data')
        return -1


def dcamtest_thread_live(dcam: Dcam):
    """Show live images.

    Capture and show live images.

    Args:
        dcam (Dcam): Dcam instance.
    
    Returns:
        Nothing.
    """
    if dcam.cap_start():

        timeout_milisec = 100
        iWindowStatus = 0
        while iWindowStatus >= 0:
            if dcam.wait_capevent_frameready(timeout_milisec):
                data = dcam.buf_getlastframedata()
                iWindowStatus = dcamtest_show_framedata(data, 'test', iWindowStatus)
            else:
                dcamerr = dcam.lasterr()
                if dcamerr.is_timeout():
                    print('===: timeout')
                else:
                    print('-NG: Dcam.wait_event() fails with error {}'.format(dcamerr))
                    break

            key = cv2.waitKey(1)
            if key == ord('q') or key == ord('Q'):  # if 'q' was pressed with the live window, close it
                break

        dcam.cap_stop()
    else:
        print('-NG: Dcam.cap_start() fails with error {}'.format(dcam.lasterr()))


def dcam_live_capturing(iDevice=0):
    """Capture live images.
    
    Recognize camera and capture live images.

    Args:
        iDevice (int): Device index.

    Returns:
        Nothing.
    """
    if Dcamapi.init():
        dcam = Dcam(iDevice)
        if dcam.dev_open():
            if dcam.buf_alloc(3):
                # th = threading.Thread(target=dcamtest_thread_live, args=(dcam,))
                # th.start()
                # th.join()
                dcamtest_thread_live(dcam)

                # release buffer
                dcam.buf_release()
            else:
                print('-NG: Dcam.buf_alloc(3) fails with error {}'.format(dcam.lasterr()))
            dcam.dev_close()
        else:
            print('-NG: Dcam.dev_open() fails with error {}'.format(dcam.lasterr()))
    else:
        print('-NG: Dcamapi.init() fails with error {}'.format(Dcamapi.lasterr()))

    Dcamapi.uninit()


if __name__ == '__main__':
    dcam_live_capturing()
