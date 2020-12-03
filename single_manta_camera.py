from vimba import *
import cv2 as cv2
import os
import time
import threading
from typing import Optional
import sys
import argparse


def print_camera(cam: Camera):
    print('/// Camera Name   : {}'.format(cam.get_name()))
    print('/// Model Name    : {}'.format(cam.get_model()))
    print('/// Camera ID     : {}'.format(cam.get_id()))
    print('/// Serial Number : {}'.format(cam.get_serial()))


def abort(reason: str, return_code: int = 1, usage: bool = False):
    print(reason + '\n')
    sys.exit(return_code)


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


# def get_camera(camera_idx: Optional[int]) -> Camera:
#     with Vimba.get_instance() as vimba:
#         cams = vimba.get_all_cameras()
#         if camera_idx >= 0:
#             try:
#                 return cams[camera_idx]
#
#             except VimbaCameraError:
#                 abort('Failed to access Camera \'{}\'. Abort.'.format(camera_idx))
#
#         else:
#             abort('Unsupported camera index. Abort.')
#             try:
#                 return cams[0]
#             except VimbaCameraError:
#                 abort('No camera can be accessed! Abort.')


def setup_camera(cam: Camera, image_size: (2048, 2048)):
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

        # Try to acquire camera bandwidth and allocate it at maximum
        try:
            stream_speed = cam.get_feature_by_name('StreamBytesPerSecond')
            print('=> original stream bandwidth: {}'.format(stream_speed.get()))
            stream_speed.set(stream_speed.get_range()[1])
            print('=> stream bandwidth have been allocated in maximum ({})'.format(stream_speed.get()))
        except (ArithmeticError, VimbaFeatureError):
            pass

        # Try to set image size
        try:

            width = cam.get_feature_by_name('Width')
            print('=> original image width: {}'.format(width.get()))
            if width.get() != image_size[0]:
                width.set(image_size[0])
                print('=> the width of camera image is set to {}'.format(width.get()))
                while not width.is_done():
                    pass
        except (AttributeError, VimbaFeatureError):
            pass

        # Try to set image height
        try:
            height = cam.get_feature_by_name('Height')
            if height.get() != image_size[1]:
                height.set(image_size[1])
                print('=> the height of camera image is set to {}'.format(height.get()))
                while not width.is_done():
                    pass
        except (AttributeError, VimbaFeatureError):
            pass

        # Try to acquire camera frame rate and allocate it at maximum
        try:
            frame_rate = cam.get_feature_by_name('AcquisitionFrameRateAbs')
            frame_rate_limt = cam.get_feature_by_name('AcquisitionFrameRateLimit')
            print('=> original camera frame rate: {:.2f} / {:.2f}'.format(frame_rate.get(), frame_rate_limt.get()))
            frame_rate.set(frame_rate_limt.get() - 1)
            print('=> successfully set camera frame rate at {:.2f} fps'.format(frame_rate.get()))
            while not frame_rate.is_done():
                pass
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
            print('{} acquired {}: ({}, {})'.format(cam, frame, frame.get_width(), frame.get_height()), flush=True)

            msg = 'Stream from \'{}\'. Press <Enter> to stop stream.'
            cv2.namedWindow(msg.format(cam.get_name()), cv2.WINDOW_GUI_EXPANDED)
            cv2.putText(image, 'Frame: {:0.1f}/{:0.1f}'.format(frame_rate, frame_rate_limt), org=(30, 50),
                       fontScale=3, color=255, thickness=3, fontFace=cv2.FONT_HERSHEY_COMPLEX_SMALL)
            cv2.imshow(msg.format(cam.get_name()), image)

        cam.queue_frame(frame)


parser = argparse.ArgumentParser('Single camera capture')
parser.add_argument('--cam_idx', type=int, default=0, help='the index of camera')
parser.add_argument('--cam_id', type=str, default='DEV_000F314EC109', help='the ID of camera')
parser.add_argument('--image_size', type=tuple, default=(2048, 2048), help='the size of acquired image')
args = parser.parse_args()

if __name__ == '__main__':
    cam_id = args.cam_id
    cam_idx = args.cam_idx
    with Vimba.get_instance() as vimba:
        with get_camera(cam_id) as cam:
            print_camera(cam)
            # setup camera
            setup_camera(cam, args.image_size)
            # state handler instance
            handler = Handler()

            try:
                # start streaming
                cam.start_streaming(handler=handler, buffer_count=2)
                handler.shutdown_event.wait()
            finally:
                cam.stop_streaming()





