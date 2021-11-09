#! /usr/bin/env python
import os
import pdb
import sys
import numpy as np
import threading
import copy
import rospy
import tf
import tf.transformations as tr
import argparse

from bubble_control.bubble_data_collection.bubble_draw_data_collection import BubbleDrawingDataCollection

# TEST THE CODE: ------------------------------------------------------------------------------------------------------


def collect_data_drawing_test(save_path, scene_name, num_data=10, prob_axis=0.08, impedance_mode=False, reactive=False, drawing_area_center=(0.55, 0.), drawing_area_size=(.15, .15), drawing_length_limits=(0.01, 0.15)):

    dc = BubbleDrawingDataCollection(data_path=save_path,
                                     scene_name=scene_name,
                                     prob_axis=prob_axis,
                                     impedance_mode=impedance_mode,
                                     reactive=reactive,
                                     drawing_area_center=drawing_area_center,
                                     drawing_area_size=drawing_area_size,
                                     drawing_length_limits=drawing_length_limits)
    dc.collect_data(num_data=num_data)


if __name__ == '__main__':

    parser = argparse.ArgumentParser('Collect Data Drawing')
    parser.add_argument('save_path', type=str, help='path to save the data')
    parser.add_argument('num_data', type=int, help='Number of data samples to be collected')
    parser.add_argument('--scene_name', type=str, default='drawing_data', help='scene name for the data. For organization purposes')
    parser.add_argument('--prob_axis', type=float, default=0.08, help='probability for biasing the drawing along the axis')
    parser.add_argument('--impedance', action='store_true', help='impedance mode')
    parser.add_argument('--reactive', action='store_true', help='reactive mode -- adjust tool position to be straight when we start drawing')
    parser.add_argument('--drawing_area_center', type=float, nargs=2, default=(0.55, 0.), help='x y of the drawing area center')
    parser.add_argument('--drawing_area_size', type=float, nargs=2, default=(0.15, 0.15), help='delta_x delta_y of the semiaxis drawing area')
    parser.add_argument('--drawing_length_limits', type=float, nargs=2, default=(0.01, 0.15), help='min_length max_length of the drawing move')

    args = parser.parse_args()

    save_path = args.save_path
    scene_name = args.scene_name
    num_data = args.num_data
    prob_axis = args.prob_axis
    impedance_mode = args.impedance
    reactive = args.reactive
    drawing_area_center = args.drawing_area_center
    drawing_area_size = args.drawing_area_size
    drawing_length_limits = args.drawing_length_limits

    collect_data_drawing_test(save_path, scene_name, num_data=num_data, prob_axis=prob_axis,
                              impedance_mode=impedance_mode, reactive=reactive, drawing_area_center=drawing_area_center,
                              drawing_area_size=drawing_area_size, drawing_length_limits=drawing_length_limits)