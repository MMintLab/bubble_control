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

from bubble_control.bubble_data_collection.med_wrench_data_collection import MedWrenchDataCollection

# TEST THE CODE: ------------------------------------------------------------------------------------------------------


def collect_data_med_wrench_test(supervision=False, reactive=False):

    save_path = '/home/mik/Desktop/medusa_wrench_zero_tool'
    scene_name = 'wrench_scene'

    dc = MedWrenchDataCollection(data_path=save_path, scene_name=scene_name, supervision=False)
    dc.collect_data(num_data=15)


if __name__ == '__main__':
    collect_data_med_wrench_test()