import abc
import torch
import numpy as np
import copy
import tf.transformations as tr
from pytorch_mppi import mppi
import pytorch3d.transforms as batched_trs

from bubble_control.bubble_model_control.aux.bubble_model_control_utils import batched_tensor_sample, get_transformation_matrix, tr_frame, convert_all_tfs_to_tensors


def drawing_action_model_one_dir(state_samples, actions):
    """
    ACTION MODEL FOR BubbleOneDirectionDrawingEnv.
    Simulates the effects of an action to the tfs.
    :param state_samples: dictionary of batched states representing a sample of a state
    :param actions: batched actions to be applied to the state_sample
    :return:
    """
    state_samples_corrected = state_samples
    action_names = ['rotation', 'length', 'grasp_width']
    rotations = actions[..., 0]
    lengths = actions[..., 1]
    grasp_widths = actions[..., 2] * 0.001  # the action grasp width is in mm
    # Rotation is a rotation about the x axis of the grasp_frame
    # Length is a translation motion of length 'length' of the grasp_frame on the xy med_base plane along the intersection with teh yz grasp frame plane
    # grasp_width is the width of the
    all_tfs = state_samples_corrected['all_tfs']  # Tfs from world frame ('med_base') to the each of teh frame names
    frame_names = all_tfs.keys()

    rigid_ee_frames = ['grasp_frame', 'med_kuka_link_ee', 'wsg50_finger_left', 'pico_flexx_left_link',
                       'pico_flexx_left_optical_frame', 'pico_flexx_right_link', 'pico_flexx_right_optical_frame']
    wf_X_gf = all_tfs['grasp_frame']
    # Move Gripper:
    # (move wsg_50_finger_{right,left} along x direction)
    gf_X_fl = get_transformation_matrix(all_tfs, 'grasp_frame', 'wsg50_finger_left')
    gf_X_fr = get_transformation_matrix(all_tfs, 'grasp_frame', 'wsg50_finger_right')
    X_finger_left = torch.eye(4).unsqueeze(0).repeat_interleave(actions.shape[0], dim=0).type(torch.double)
    X_finger_right = torch.eye(4).unsqueeze(0).repeat_interleave(actions.shape[0], dim=0).type(torch.double)
    current_half_width_l = -gf_X_fl[..., 0, 3] - 0.009
    current_half_width_r = gf_X_fr[..., 0, 3] - 0.009
    X_finger_left[..., 0, 3] = -(0.5 * grasp_widths - current_half_width_l).type(torch.double)
    X_finger_right[..., 0, 3] = -(0.5 * grasp_widths - current_half_width_r).type(torch.double)
    all_tfs = tr_frame(all_tfs, 'wsg50_finger_left', X_finger_left,
                       ['pico_flexx_left_link', 'pico_flexx_left_optical_frame'])
    all_tfs = tr_frame(all_tfs, 'wsg50_finger_right', X_finger_right,
                       ['pico_flexx_right_link', 'pico_flexx_right_optical_frame'])
    # Move Grasp frame on the plane amount 'length; and rotate the Grasp frame along x direction a 'rotation'  amount
    rot_axis = torch.tensor([1, 0, 0]).unsqueeze(0).repeat_interleave(actions.shape[0], dim=0).type(torch.double)
    angle_axis = rotations.unsqueeze(-1).repeat_interleave(3, dim=-1) * rot_axis
    X_gf_rot = torch.eye(4).unsqueeze(0).repeat_interleave(actions.shape[0], dim=0).type(torch.double)
    X_gf_rot[..., :3, :3] = batched_trs.axis_angle_to_matrix(angle_axis)  # rotation along x axis
    # compute translation
    z_axis = torch.tensor([0, 0, 1]).unsqueeze(0).repeat_interleave(actions.shape[0], dim=0).type(torch.double)
    y_dir_gf = torch.tensor([0, -1, 0]).unsqueeze(0).repeat_interleave(actions.shape[0], dim=0).type(torch.double)
    y_dir_wf = torch.einsum('kij,kj->ki', wf_X_gf[..., :3, :3], y_dir_gf)
    y_dir_wf_perp = torch.einsum('ki,ki->k', y_dir_wf, z_axis).unsqueeze(-1).repeat_interleave(3, dim=-1) * z_axis
    drawing_dir_wf = y_dir_wf - y_dir_wf_perp
    drawing_dir_wf = drawing_dir_wf / torch.linalg.norm(drawing_dir_wf, dim=1).unsqueeze(-1).repeat_interleave(3,
                                                                                                               dim=-1)  # normalize
    drawing_dir_gf = torch.einsum('kij,kj->ki', torch.linalg.inv(wf_X_gf[..., :3, :3]), drawing_dir_wf)
    trans_gf = lengths.unsqueeze(-1).repeat_interleave(3, dim=-1) * drawing_dir_gf
    X_gf_trans = torch.eye(4).unsqueeze(0).repeat_interleave(actions.shape[0], dim=0).type(torch.double).type(
        torch.double)
    X_gf_trans[..., :3, 3] = trans_gf
    all_tfs = tr_frame(all_tfs, 'grasp_frame', X_gf_trans, rigid_ee_frames)
    all_tfs = tr_frame(all_tfs, 'grasp_frame', X_gf_rot, rigid_ee_frames)
    state_samples_corrected['all_tfs'] = all_tfs

    return state_samples_corrected