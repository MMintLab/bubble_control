import torch
import os
from bubble_utils.bubble_datasets.transform_processed_dataset import transform_processed_dataset
from bubble_control.aux.load_confs import load_object_models as load_object_models_drawing
from bubble_pivoting.aux.load_confs import load_object_models as load_object_models_pivoting
from bubble_control.bubble_learning.datasets.bubble_drawing_dataset import BubbleDrawingDataset
from bubble_pivoting.datasets.bubble_pivoting_dataset import BubblePivotingDataset, BubblePivotingDownsampledDataset
from bubble_utils.bubble_datasets.data_transformations import TensorTypeTr


class ReplaceObjectTr(object):
    def __init__(self, new_object_models):
        self.new_object_models = new_object_models

    def __call__(self, sample):
        object_code = sample['object_code']
        new_object_model = self.new_object_models[object_code]
        sample['object_model'] = new_object_model
        return sample


def replace_drawing_object_models(data_name):
    drawing_models = load_object_models_drawing()
    tensor_type_tr = TensorTypeTr(dtype=torch.float32)
    replace_obj_tr = ReplaceObjectTr(drawing_models)
    dataset = BubbleDrawingDataset(
        data_name=data_name,
        downsample_factor_x=7,
        downsample_factor_y=7,
        downsample_reduction='mean')
    trs = [replace_obj_tr, tensor_type_tr]
    transform_processed_dataset(dataset, trs)


def replace_pivoting_object_models(data_name):
    pivoting_models = load_object_models_pivoting()
    tensor_type_tr = TensorTypeTr(dtype=torch.float32)
    replace_obj_tr = ReplaceObjectTr(pivoting_models)
    dataset = BubblePivotingDownsampledDataset(
        data_name=data_name,
        downsample_factor_x=7,
        downsample_factor_y=7,
        downsample_reduction='mean')
    trs = [replace_obj_tr, tensor_type_tr]
    transform_processed_dataset(dataset, trs)


if __name__ == '__main__':
    data_path = '/home/mik/Datasets/bubble_datasets'

    replace_drawing_object_models(os.path.join(data_path, 'drawing_data_one_direction'))
    replace_drawing_object_models(os.path.join(data_path, 'drawing_data_line'))
    replace_pivoting_object_models(os.path.join(data_path, 'bubble_pivoting_data'))