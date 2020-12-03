"""BSD 2-Clause License

Copyright (c) 2019, Allied Vision Technologies GmbH
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

THE SOFTWARE IS PRELIMINARY AND STILL IN TESTING AND VERIFICATION PHASE AND
IS PROVIDED ON AN “AS IS” AND “AS AVAILABLE” BASIS AND IS BELIEVED TO CONTAIN DEFECTS.
A PRIMARY PURPOSE OF THIS EARLY ACCESS IS TO OBTAIN FEEDBACK ON PERFORMANCE AND
THE IDENTIFICATION OF DEFECT SOFTWARE, HARDWARE AND DOCUMENTATION.
"""
import threading
import sys
import cv2
from typing import Optional
from vimba import *

global MAX_BANDWIDTH
MAX_BANDWIDTH = 115000000


def print_preamble():
    print('///////////////////////////////////////////////////////')
    print('/// Vimba API Asynchronous Grab with OpenCV Example ///')
    print('///////////////////////////////////////////////////////\n')


def print_usage():
    print('Usage:')
    print('    python asynchronous_grab_opencv.py [camera_id]')
    print('    python asynchronous_grab_opencv.py [/h] [-h]')
    print()
    print('Parameters:')
    print('    camera_id   ID of the camera to use (using first camera if not specified)')
    print()


def abort(reason: str, return_code: int = 1, usage: bool = False):
    print(reason + '\n')

    if usage:
        print_usage()

    sys.exit(return_code)


def parse_args() -> Optional[str]:
    args = sys.argv[1:]
    argc = len(args)

    for arg in args:
        if arg in ('/h', '-h'):
            print_usage()
            sys.exit(0)

    if argc > 1:
        abort(reason="Invalid number of arguments. Abort.", return_code=2, usage=True)

    return None if argc == 0 else args[0]


def get_camera(camera_id: Optional[str]) -> Camera:
    with Vimba.get_instance() as vimba:
        if camera_id:
            try:
                return vimba.get_camera_by_id(camera_id)

            except VimbaCameraError:
                abort('Failed to access Camera \'{}\'. Abort.'.format(camera_id))

        else:
            cams = vimba.get_all_cameras()
            if not cams:
                abort('No Cameras accessible. Abort.')

            return cams[0]


def setup_camera(cam: Camera):
    with cam:
        # Disable auto exposure time setting
        try:
            cam.ExposureAuto.set('Off')
            exposure_time = cam.get_feature_by_name('ExposureTimeAbs')
            exposure_time.set(15000)

        except (AttributeError, VimbaFeatureError):
            pass

        # Enable white balancing if camera supports it
        try:
            cam.BalanceWhiteAuto.set('Continuous')

        except (AttributeError, VimbaFeatureError):
            pass

        # Try to adjust GeV packet size. This Feature is only available for GigE - Cameras.
        try:
            cam.GVSPAdjustPacketSize.run()

            while not cam.GVSPAdjustPacketSize.is_done():
                pass

        except (AttributeError, VimbaFeatureError):
            pass

        # Try to modify Gev stream speed
        try:
            stream_speed = cam.get_feature_by_name('StreamBytesPerSecond')
            print('=> original stream bandwidth: {}'.format(stream_speed.get()))
            stream_speed.set(stream_speed.get_range()[1])
            print('=> stream bandwidth have been allocated in maximum ({})'.format(stream_speed.get()))

        except (ArithmeticError, VimbaFeatureError):
            pass

        # Try to modify Gev frame rate.
        try:
            frame_rate = cam.get_feature_by_name('AcquisitionFrameRateAbs')
            frame_rate_limt = cam.get_feature_by_name('AcquisitionFrameRateLimit')
            print('=> orginal camera frame rate: {:.2f} / {:.2f}'.format(frame_rate.get(), frame_rate_limt.get()))
            if frame_rate.get() < frame_rate_limt.get():
                frame_rate.set(frame_rate_limt.get() - 1)
                print('=> successfully set camera frame rate at {:.2f} fps'.format(frame_rate.get()))

        except (AttributeError, VimbaFeatureError):
            pass

        # Query available, open_cv compatible pixel formats
        # prefer color formats over monochrome formats
        cv_fmts = intersect_pixel_formats(cam.get_pixel_formats(), OPENCV_PIXEL_FORMATS)
        color_fmts = intersect_pixel_formats(cv_fmts, COLOR_PIXEL_FORMATS)

        if color_fmts:
            cam.set_pixel_format(color_fmts[0])

        else:
            mono_fmts = intersect_pixel_formats(cv_fmts, MONO_PIXEL_FORMATS)

            if mono_fmts:
                cam.set_pixel_format(mono_fmts[0])

            else:
                abort('Camera does not support a OpenCV compatible format natively. Abort.')


class Handler:
    def __init__(self):
        self.shutdown_event = threading.Event()

    def __call__(self, cam: Camera, frame: Frame):
        ENTER_KEY_CODE = 13
        frame_rate = cam.get_feature_by_name('AcquisitionFrameRateAbs').get()
        frame_rate_limt = cam.get_feature_by_name('AcquisitionFrameRateLimit').get()

        key = cv2.waitKey(1)
        if key == ENTER_KEY_CODE:
            self.shutdown_event.set()
            return

        elif frame.get_status() == FrameStatus.Complete:
            image = frame.as_opencv_image()
            print('{} acquired {}'.format(cam, frame), flush=True)
            msg = 'Stream from \'{}\'. Press <Enter> to stop stream.'
            cv2.namedWindow(msg.format(cam.get_name()), cv2.WINDOW_GUI_EXPANDED)
            cv2.putText(image, 'Frame: {:0.1f}/{:0.1f}'.format(frame_rate, frame_rate_limt), org=(30, 30),
                        fontScale=1, color=255, thickness=1, fontFace=cv2.FONT_HERSHEY_COMPLEX_SMALL)
            cv2.imshow(msg.format(cam.get_name()), image)

        cam.queue_frame(frame)


def main():
    print_preamble()
    # cam_id = parse_args()
    cam_id = 'DEV_000F314EC10A'
    with Vimba.get_instance():
        with get_camera(cam_id) as cam:

            # Start Streaming, wait for five seconds, stop streaming
            setup_camera(cam)
            handler = Handler()

            try:
                # Start Streaming with a custom a buffer of 10 Frames (defaults to 5)
                cam.start_streaming(handler=handler, buffer_count=1)
                handler.shutdown_event.wait()

            finally:
                cam.stop_streaming()


if __name__ == '__main__':
    main()
