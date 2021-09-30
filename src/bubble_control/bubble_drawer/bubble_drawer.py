#! /usr/bin/env python
import numpy as np
import rospy
import tf
import tf.transformations as tr

from arm_robots.med import Med
from arc_utilities.listener import Listener
from arc_utilities.tf2wrapper import TF2Wrapper
from victor_hardware_interface.victor_utils import Stiffness
from victor_hardware_interface_msgs.msg import ControlMode

from geometry_msgs.msg import WrenchStamped
from visualization_msgs.msg import Marker


class BubbleDrawer(object):

    def __init__(self, object_topic='estimated_object', wrench_topic='/med/wrench', force_threshold=5., reactive=False):
        self.object_topic = object_topic
        self.wrench_topic = wrench_topic
        self.reactive = reactive
        self.force_threshold = force_threshold
        # Parameters:
        self.draw_contact_gap = 0.005  # TODO: Consider reducing this value to reduce the force
        self.pre_height = 0.13
        self.draw_height_limit = 0.075  # we could go as lower as 0.06
        self.draw_quat = np.array([-np.cos(np.pi / 4), np.cos(np.pi / 4), 0, 0])
        # Init ROS node
        try:
            rospy.init_node('drawing_test')
        except (rospy.exceptions.ROSInitException, rospy.exceptions.ROSException):
            pass
        self.tf_listener = tf.TransformListener()
        self.med = Med(display_goals=False)
        self.marker_pose = None
        self.calibrated_wrench = None
        self.pose_listener = Listener(self.object_topic, Marker, wait_for_data=False)
        self.wrench_listener = Listener(self.wrench_topic, WrenchStamped, wait_for_data=True)
        self.tf2_listener = TF2Wrapper()
        self.tf_broadcaster = tf.TransformBroadcaster()
        # Set up the robot
        self._setup()

    def home_robot(self):
        # self.med.plan_to_joint_config(self.med.arm_group, [0, 1.0, 0, -0.8, 0, 0.9, 0])
        self.med.plan_to_joint_config(self.med.arm_group, [0, 0.432, 0, -1.584, 0, 0.865, 0])

    def set_grasp_pose(self):
        grasp_pose_joints = [0.7613740469101997, 1.1146166859754167, -1.6834551714751782, -1.6882417308401203,
                             0.47044861033517205, 0.8857417788890095, 0.8497585444122142]
        self.med.plan_to_joint_config(self.med.arm_group, grasp_pose_joints)

    def _setup(self):
        self.med.connect()
        self.med.set_control_mode(ControlMode.JOINT_POSITION, vel=0.1)

        # Set the robot to a favorable position so we can start the impedance mode
        self.home_robot()
        # self.med.plan_to_pose(self.med.arm_group, self.med.wrist, target_pose=[0.6, 0.0, 0.4, 0.0, np.pi - 0.2, 0.0], frame_id="world")
        # self.med.set_control_mode(ControlMode.JOINT_IMPEDANCE, stiffness=Stiffness.STIFF, vel=0.075)  # Low vel for safety
        # self.med.set_control_mode(ControlMode.JOINT_POSITION, vel=0.05)  # Low vel for safety

        self.calibrated_wrench = self._get_wrench()

    def _get_wrench(self):
        wrench_stamped_wrist = self.wrench_listener.get(block_until_data=True)
        wrench_stamped = self.tf2_listener.transform_to_frame(wrench_stamped_wrist, target_frame="world",
                                                              timeout=rospy.Duration(nsecs=int(5e8)))
        return wrench_stamped

    def _stop_signal(self, feedback):
        wrench_stamped = self._get_wrench()
        measured_fz = wrench_stamped.wrench.force.z
        calibrated_fz = measured_fz-self.calibrated_wrench.wrench.force.z
        flag_force = np.abs(calibrated_fz) >= np.abs(self.force_threshold)
        if flag_force:
            print('force z: {} (measured: {}) --- flag: {} ({} | {})'.format(calibrated_fz, measured_fz, flag_force, np.abs(calibrated_fz), np.abs(self.force_threshold)))
        return flag_force

    def get_marker_pose(self):
        data = self.pose_listener.get(block_until_data=True)
        pose = [data.pose.position.x,
                data.pose.position.y,
                data.pose.position.z,
                data.pose.orientation.x,
                data.pose.orientation.y,
                data.pose.orientation.z,
                data.pose.orientation.w
                ]
        marker_pose = {
            'pose': pose,
            'frame': data.header.frame_id,
        }
        return marker_pose

    def test_pivot_motion(self):
        world_frame_name = 'med_base'
        contact_point_frame_name = 'tool_contact_point'
        tool_frame_name = 'tool_frame'
        tool_frame_desired_quat = np.array([-np.cos(np.pi/4), np.cos(np.pi/4), 0, 0]) # desired quaternion in the world frame (med_base)
        contact_frame_wf = self.tf2_listener.get_transform(parent=world_frame_name, child=contact_point_frame_name)
        tool_frame_cpf = self.tf2_listener.get_transform(parent=contact_point_frame_name, child=tool_frame_name) # tool frame on the contact point frame
        tool_frame_gf = self.tf2_listener.get_transform(parent='grasp_frame', child=tool_frame_name) # tool frame on grasp frame

        tool_frame_t_cpf = tool_frame_cpf[:3,3]
        final_axis_t_cpf = np.array([0,0,1])
        _desired_tool_cf = tr.quaternion_matrix(tool_frame_desired_quat)
        _desired_tool_cf[:3,3] = final_axis_t_cpf * np.linalg.norm(tool_frame_t_cpf)
        desired_tool_cf = _desired_tool_cf
        desired_tool_wf = contact_frame_wf @ desired_tool_cf # w_T_cf @ cf_T_dtf = w_T_dtf
        desired_grasp_frame_wf = desired_tool_wf @ tr.inverse_matrix(tool_frame_gf)# w_T_gf = w_T_dtf @ dtf_T_gf
        desired_grasp_pose = list(desired_grasp_frame_wf[:3,3]) + list(tr.quaternion_from_matrix(desired_grasp_frame_wf))
        desired_tool_pose = list(desired_tool_wf[:3,3]) + list(tr.quaternion_from_matrix(desired_tool_wf))
        # try all at one:
        self.med.set_execute(False)
        plan_result = self.med.plan_to_pose(self.med.arm_group, 'grasp_frame', target_pose=desired_grasp_pose, frame_id=world_frame_name)
        self.med.set_execute(True)
        self.tf2_listener.send_transform(translation=desired_grasp_pose[:3], quaternion=desired_grasp_pose[3:], parent=world_frame_name, child='desired_grasp_frame_pivot', is_static=True)
        self.tf2_listener.send_transform(translation=desired_tool_pose[:3], quaternion=desired_tool_pose[3:], parent=world_frame_name, child='desired_tool_frame_pivot', is_static=True)
        _ = input('press enter to execute')
        self.med.follow_arms_joint_trajectory(plan_result.planning_result.plan.joint_trajectory,
                                                  stop_condition=self._stop_signal)

    def _init_drawing(self, init_point_xy, draw_quat=None, ref_frame=None):
        # Plan to the point_xy and perform a guarded move to start drawing
        # Variables:
        pre_height = self.pre_height
        draw_height_limit = self.draw_height_limit
        draw_height = draw_height_limit
        if draw_quat is None:
            draw_quat = self.draw_quat
        ref_frame = 'med_base'

        # first plan to the first corner
        pre_position = np.insert(init_point_xy, 2, pre_height)
        pre_pose = np.concatenate([pre_position, draw_quat], axis=0)

        if self.reactive:
            desired_pose = pre_pose
            T_desired = tr.quaternion_matrix(draw_quat)  # in world frame
            T_desired[:3, 3] = pre_position
            current_marker_pose = self.get_marker_pose()
            T_mf = tr.quaternion_matrix(current_marker_pose['pose'][3:])  # marker frame in grasp frame
            T_mf[:3, 3] = current_marker_pose['pose'][:3]
            T_mf_desired = T_desired @ np.linalg.inv(T_mf)
            target_pose = np.concatenate([T_mf_desired[:3, 3], tr.quaternion_from_matrix(T_mf_desired)])
            self.tf_broadcaster.sendTransform(list(target_pose[:3]), list(target_pose[3:]), rospy.Time.now(),
                                              '{}_desired'.format(current_marker_pose['frame']), ref_frame)

            self.tf_broadcaster.sendTransform(list(desired_pose[:3]), list(desired_pose[3:]), rospy.Time.now(),
                                              'desired_obj_pose', ref_frame)
            self.tf_broadcaster.sendTransform(list(current_marker_pose['pose'][:3]),
                                              list(current_marker_pose['pose'][3:]), rospy.Time.now(),
                                              'current_obj_pose', current_marker_pose['frame'])
            self.med.plan_to_pose(self.med.arm_group, current_marker_pose['frame'], target_pose=list(target_pose),
                                  frame_id='med_base')

        else:
            self.med.plan_to_pose(self.med.arm_group, 'grasp_frame', target_pose=list(pre_pose), frame_id='med_base')
        # self.med.set_control_mode(ControlMode.JOINT_IMPEDANCE, stiffness=Stiffness.STIFF, vel=0.075)  # Low val for safety
        rospy.sleep(.5)
        self.med.set_control_mode(ControlMode.JOINT_IMPEDANCE, stiffness=Stiffness.STIFF,
                                  vel=0.03)  # Very Low val for precision

        # lower down:
        position_0 = np.insert(init_point_xy, 2, 0.065)
        pose_0 = np.concatenate([position_0, draw_quat], axis=0)
        self.force_threshold = 5.
        self.med.set_execute(False)
        plan_result = self.med.plan_to_position_cartesian(self.med.arm_group, 'grasp_frame',
                                                          target_position=list(position_0))
        self.med.set_execute(True)
        self.med.follow_arms_joint_trajectory(plan_result.planning_result.plan.joint_trajectory,
                                              stop_condition=self._stop_signal)
        rospy.sleep(.5)
        # Read the value of z when we make contact to only set a slight force on the plane
        contact_pose = self.tf2_listener.get_transform('med_base', 'grasp_frame')
        draw_contact_gap = 0.005  # TODO: Consider reducing this value to reduce the force
        draw_height = max(contact_pose[2, 3] - draw_contact_gap, draw_height_limit)
        # read force
        first_contact_wrench = self._get_wrench()
        print('contact wrench: ', first_contact_wrench.wrench)
        self.force_threshold = 18  # Increase the force threshold

        self.med.set_control_mode(ControlMode.JOINT_IMPEDANCE, stiffness=Stiffness.STIFF, vel=0.1)  # change speed
        return draw_height

    def _draw_to_point(self, point_xy, draw_height, end_raise=False):
        position_i = np.insert(point_xy, 2, draw_height)
        self.med.set_execute(False)
        plan_result = self.med.plan_to_position_cartesian(self.med.arm_group, 'grasp_frame',
                                                          target_position=list(position_i))
        self.med.set_execute(True)
        execution_result = self.med.follow_arms_joint_trajectory(plan_result.planning_result.plan.joint_trajectory,
                                                                 stop_condition=self._stop_signal)
        plan_success = plan_result.success
        execution_success = execution_result.success
        if not plan_success:
            print('@' * 20 + '    Plan Failed    ' + '@' * 20)
            import pdb; pdb.set_trace()
        if not execution_success:
            # It seams tha execution always fails (??)
            print('-' * 20 + '    Execution Failed    ' + '-' * 20)

        if end_raise:
            # Raise the arm when we reach the last point
            self._end_raise(point_xy)


    def _end_raise(self, point_xy):
        final_position = np.insert(point_xy, 2, self.pre_height)
        final_pose = np.concatenate([final_position, self.draw_quat], axis=0)
        self.med.plan_to_pose(self.med.arm_group, 'grasp_frame', target_pose=list(final_pose), frame_id='med_base')

    def _adjust_tool_position(self, xy_point):
        # Adjust the position when we reach the keypoint -------
        # Lift:
        draw_quat = self.draw_quat
        lift_position = np.insert(xy_point, 2, self.pre_height)
        self.med.plan_to_position_cartesian(self.med.arm_group, 'grasp_frame', target_position=list(lift_position))

        # compensate for the orientation of the marker
        T_desired = tr.quaternion_matrix(draw_quat)
        T_desired[:3, 3] = lift_position
        current_marker_pose = self.get_marker_pose()
        T_mf = tr.quaternion_matrix(current_marker_pose['pose'][3:])
        T_mf[:3, 3] = current_marker_pose['pose'][:3]
        T_mf_desired = T_desired @ np.linalg.inv(T_mf)  # maybe it is this
        # Compute the target and account for tool pose
        target_pose = np.concatenate([T_mf_desired[:3, 3], tr.quaternion_from_matrix(T_mf_desired)])
        plan_result = self.med.plan_to_pose(self.med.arm_group, current_marker_pose['frame'],
                                            target_pose=list(target_pose), frame_id='med_base')
        # Go down again
        rospy.sleep(.5)
        self.med.set_control_mode(ControlMode.JOINT_IMPEDANCE, stiffness=Stiffness.STIFF,
                                  vel=0.05)  # Very Low val for precision
        # lower down:
        lower_position = np.insert(xy_point, 2, 0.065)
        lower_pose = np.concatenate([lower_position, draw_quat], axis=0)
        self.force_threshold = 5.
        self.med.set_execute(False)
        plan_result = self.med.plan_to_position_cartesian(self.med.arm_group, 'grasp_frame',
                                                          target_position=list(lower_position))
        self.med.set_execute(True)
        self.med.follow_arms_joint_trajectory(plan_result.planning_result.plan.joint_trajectory,
                                              stop_condition=self._stop_signal)
        rospy.sleep(.5)
        # Read the value of z when we make contact to only set a slight force on the plane
        contact_pose = self.tf2_listener.get_transform('med_base', 'grasp_frame')
        draw_height = max(contact_pose[2, 3] - self.draw_contact_gap, self.draw_height_limit)
        # read force
        first_contact_wrench = self._get_wrench()
        print('contact wrench: ', first_contact_wrench.wrench)
        self.force_threshold = 18  # Increase the force threshold
        self.med.set_control_mode(ControlMode.JOINT_IMPEDANCE, stiffness=Stiffness.STIFF, vel=0.1)
        rospy.sleep(.5)

    def draw_points(self, xy_points, end_raise=True):
        """
        Draw lines between a series of xy points. The robot executes cartesian trajectories on impedance mode between all points on the list
        Args:
            xy_points: <np.ndarray> of size (N,2) containing the N points on the xy plane we want to be drawn

        Returns: None
        """

        # TODO: Split into guarded moved motion and drawing_motion between points

        draw_height = self._init_drawing(init_point_xy=xy_points[0])

        rospy.sleep(.5)
        for i, corner_i in enumerate(xy_points[1:]):

            self._draw_to_point(corner_i, draw_height, end_raise=False)

            if self.reactive and (i < len(xy_points)-2):
                # Adjust the position when we reach the keypoint -------
                self._adjust_tool_position(corner_i)

        if end_raise:
            # Raise the arm when we reach the last point
            final_position = np.insert(xy_points[-1], 2, self.pre_height)
            final_pose = np.concatenate([final_position, self.draw_quat], axis=0)
            self.med.plan_to_pose(self.med.arm_group, 'grasp_frame', target_pose=list(final_pose), frame_id='med_base')

    def draw_square(self, side_size=0.2, center=(0.55, -0.1), step_size=None, spread_evenly=True):
        corners = np.asarray(center) + side_size * 0.5 * np.array([[1, 1], [1, -1], [-1, -1], [-1, 1], [1,1]])
        if step_size is not None:
            corners = self._discretize_points(corners, step_size=step_size, spread_evenly=spread_evenly)
        self.draw_points(corners)

    def draw_regular_polygon(self, num_sides, circumscribed_radius=0.2, center=(0.55, -0.1), init_angle=0):
        _angles = 2 * np.pi * np.arange(num_sides+1)/(num_sides)
        angles = (init_angle + _angles )%(2*np.pi)
        basic_vertices = np.stack([np.cos(angles), np.sin(angles)], axis=1)
        corners = np.asarray(center) + circumscribed_radius * 0.5 * basic_vertices
        self.draw_points(corners)

    def draw_circle(self, radius=0.2, num_points=100, center=(0.55, -0.1)):
        self.draw_regular_polygon(num_sides=num_points, circumscribed_radius=radius, center=center)

    def _discretize_points(self, points_xy, step_size=0.05, spread_evenly=True):
        """
        Given a set of points on xy plane, create a new set of points where points at most are step_size from each other
        Args:
            points_xy:
        Returns:
        """
        num_keypoints = points_xy.shape[0]
        point_dim = points_xy.shape[-1]
        discretized_points = []
        for i, point_i in enumerate(points_xy[:-1]):
            next_point = points_xy[i+1]
            delta_v = next_point - point_i
            point_dist = np.linalg.norm(delta_v)
            unit_v = delta_v/point_dist
            num_points = int(point_dist//step_size)
            if spread_evenly:
                # spread the points so they are all evenly distributed
                step_i = point_dist/num_points
            else:
                # points dist a fixed distance, except last one that has a residual distance <= step_size
                step_i = step_size
            points_i = point_i + step_i * np.stack([np.arange(num_points)]*point_dim, axis=-1) * np.stack([unit_v]*num_points)
            for new_point in points_i:
                discretized_points.append(new_point)
        discretized_points.append(points_xy[-1])
        discretized_points = np.stack(discretized_points)
        return discretized_points

    def control(self, desired_pose, ref_frame):
        """
        Adjust the robot so the object has a constant pose (target_pose) in the reference ref_frame
        Args:
            target_pose: <list> pose as [x,y,z,qw,qx,qy,qz]
            ref_frame: <str>
        """
        T_desired = tr.quaternion_matrix(desired_pose[3:])
        T_desired[:3, 3] = desired_pose[:3]
        try:
            while not rospy.is_shutdown():
                print('Control')
                # Read object position
                current_marker_pose = self.get_marker_pose()
                T_mf = tr.quaternion_matrix(current_marker_pose['pose'][3:])
                T_mf[:3,3] = current_marker_pose['pose'][:3]
                T_mf_desired = T_desired @ np.linalg.inv(T_mf)   # maybe it is this

                # Compute the target
                target_pose = np.concatenate([T_mf_desired[:3,3], tr.quaternion_from_matrix(T_mf_desired)])
                # broadcast target_pose:
                self.tf_broadcaster.sendTransform(list(target_pose[:3]), list(target_pose[3:]), rospy.Time.now(), '{}_desired'.format(current_marker_pose['frame']), ref_frame)
                self.tf_broadcaster.sendTransform(list(desired_pose[:3]), list(desired_pose[3:]), rospy.Time.now(), 'desired_obj_pose', ref_frame)
                self.tf_broadcaster.sendTransform(list(current_marker_pose['pose'][:3]), list(current_marker_pose['pose'][3:]), rospy.Time.now(), 'current_obj_pose', current_marker_pose['frame'])
                plan_result = self.med.plan_to_pose(self.med.arm_group, current_marker_pose['frame'], target_pose=list(target_pose), frame_id=ref_frame)
        except rospy.ROSInterruptException:
            pass

# TEST THE CODE: ------------------------------------------------------------------------------------------------------

def draw_test(supervision=False, reactive=False):
    bd = BubbleDrawer(reactive=reactive)
    # center = (0.55, -0.25) # good one
    center = (0.45, -0.25)
    # center_2 = (0.55, 0.2)
    center_2 = (0.45, 0.2)

    # bd.draw_square()
    # bd.draw_regular_polygon(3, center=center)
    # bd.draw_regular_polygon(4, center=center)
    # bd.draw_regular_polygon(5, center=center)
    # bd.draw_regular_polygon(6, center=center)
    for i in range(5):
        # bd.draw_square(center=center_2)
        bd.draw_regular_polygon(3, center=center, circumscribed_radius=0.15)
    # bd.draw_square(center=center, step_size=0.04)


    # bd.draw_square(center=center_2)
    # bd.draw_square(center=center_2)
    # bd.draw_square(center=center_2)
    # bd.draw_square(center=center_2, step_size=0.04)

    # bd.draw_circle()

def reactive_demo():
    bd = BubbleDrawer(reactive=True)
    center = (0.6, -0.25)
    center_2 = (0.6, 0.2)

    num_iters = 5

    for i in range(num_iters):
        bd.draw_regular_polygon(4, center=center, circumscribed_radius=0.15, init_angle=np.pi*0.25)

    _ = input('Please, rearange the marker and press enter. ')
    bd.reactive = False
    for i in range(num_iters):
        bd.draw_regular_polygon(4, center=center_2, circumscribed_radius=0.15, init_angle=np.pi*0.25)

def test_pivot():
    bd = BubbleDrawer(reactive=True)
    while True:
        _ = input('press enter to continue')
        bd.test_pivot_motion()

def draw_M():
    bd = BubbleDrawer(reactive=False, force_threshold=0.25)
    m_points = np.load('/home/mmint/InstalledProjects/robot_stack/src/bubble_control/config/M.npy')
    m_points[:,1] = m_points[:,1]*(-1)
    # scale points:
    scale = 0.25
    corner_point = np.array([.75, .1])
    R = tr.quaternion_matrix(tr.quaternion_about_axis(angle=-np.pi*0.5, axis=np.array([0, 0, 1])))[:2, :2]
    m_points_rotated = m_points @ R.T
    m_points_scaled = corner_point + scale*m_points_rotated
    m_points_scaled = np.concatenate([m_points_scaled, m_points_scaled[0:1]], axis=0)
    bd.draw_points(m_points_scaled)

if __name__ == '__main__':
    supervision = False
    reactive = True
    # reactive = False

    # topic_recorder = TopicRecorder()
    # wrench_recorder = WrenchRecorder('/med/wrench', ref_frame='world')
    # wrench_recorder.record()
    # draw_test(supervision=supervision, reactive=reactive)
    # print('drawing done')
    # wrench_recorder.stop()
    # wrench_recorder.save('~/Desktop')

    # reactive_demo()
    # test_pivot()
    draw_M()