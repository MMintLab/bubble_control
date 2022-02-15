import torch

from bubble_control.bubble_learning.models.bubble_autoencoder import BubbleAutoEncoderModel
from bubble_control.bubble_learning.datasets.bubble_drawing_dataset import BubbleDrawingDataset, BubbleDrawingDownsampledDataset, BubbleDrawingDownsampledCombinedDataset
from bubble_control.bubble_learning.models.bubble_dynamics_model import BubbleDynamicsModel
from bubble_control.bubble_learning.models.bubble_linear_dynamics_model import BubbleLinearDynamicsModel
from bubble_control.bubble_learning.models.bubble_dynamics_end2end_model import BubbleEnd2EndDynamicsModel
from bubble_control.bubble_learning.datasets.task_combined_dataset import TaskCombinedDataset
from bubble_control.bubble_learning.aux.orientation_trs import QuaternionToAxis

from bubble_control.bubble_learning.train_files.parsed_trainer import ParsedTrainer

if __name__ == '__main__':

    # params:
    trs = [QuaternionToAxis()]
    default_params = {
        'data_name' : '/home/mmint/Desktop/drawing_data_cartesian',
        # 'batch_size' : None,
        # 'val_batch_size' : None,
        # 'max_epochs' : 500,
        # 'train_fraction' : 0.8,
        # 'lr' : 1e-4,
        # 'seed' : 0,
        # 'activation' : 'relu',
        'img_embedding_size' : 20,
        # 'encoder_num_convs' : 3,
        # 'decoder_num_convs' : 3,
        # 'encoder_conv_hidden_sizes' : None,
        'decoder_conv_hidden_sizes' : [10, 50],
        # 'ks' : 3,
        # 'num_fcs' : 3,
        # 'num_encoder_fcs' : 2,
        # 'num_decoder_fcs' : 2,
        # 'fc_h_dim' : 100,
        # 'skip_layers' : None,
        # 'num_workers' : 8,
        'model': BubbleDynamicsModel.get_name(),
        'wrench_frame' : 'med_base',
        'tf_frame' : 'grasp_frame',
        'dtype' : torch.float32,
        'transformation' : trs,
        'downsample_factor_x': 7,
        'downsample_factor_y': 7,
        'downsample_reduction': 'max',

    }
    default_types = {
        'batch_size': int,
        'val_batch_size': int
    }
    Model = [BubbleAutoEncoderModel, BubbleDynamicsModel, BubbleLinearDynamicsModel, BubbleEnd2EndDynamicsModel]
    Dataset = [BubbleDrawingDataset, BubbleDrawingDownsampledDataset, BubbleDrawingDownsampledCombinedDataset, TaskCombinedDataset]
    parsed_trainer = ParsedTrainer(Model, Dataset, default_args=default_params, default_types=default_types)

    parsed_trainer.train()
