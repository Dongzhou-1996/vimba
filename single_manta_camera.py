from vimba import *
import cv2.cv2 as cv2
import os
import time


def print_camera(cam: Camera):
    print('/// Camera Name   : {}'.format(cam.get_name()))
    print('/// Model Name    : {}'.format(cam.get_model()))
    print('/// Camera ID     : {}'.format(cam.get_id()))
    print('/// Serial Number : {}'.format(cam.get_serial()))


if __name__ == '__main__':
    with Vimba.get_instance() as vimba:
        cams = vimba.get_all_cameras()
        print('Cameras found: {}'.format(len(cams)))
        for camera in cams:
            with camera as cam:
                print_camera(cam)
                while cv2.waitKey(3) != 27:
                    start_time = time.time()
                    frame = cam.get_frame()
                    frame.convert_pixel_format(PixelFormat.Bgr8)
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    print('elapsed time for image retrieve: {} s'.format(elapsed_time))
                    fps = 1.0 / elapsed_time
                    image = frame.as_opencv_image()
                    print('image shape: {}'.format(image.shape))
                    cv2.putText(image, 'FPS: {:0.3f}'.format(fps), (0, image.shape[0] - 20), cv2.FONT_HERSHEY_COMPLEX,
                                4, (255, 0, 255), 4)
                    cv2.namedWindow('single image', cv2.WINDOW_GUI_EXPANDED)
                    cv2.imshow('single image', image)



