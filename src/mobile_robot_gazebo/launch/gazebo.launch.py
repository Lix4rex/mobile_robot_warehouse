import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (AppendEnvironmentVariable, DeclareLaunchArgument,
                            IncludeLaunchDescription)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

# Pose (x, y, z, yaw) de chaque capteur dans base_link, d'après models/tugbot/model.sdf
# (pose du link + pose du capteur). Gazebo publie les données dans le repère
# <modèle>::<link>::<capteur>, que ros_gz_bridge convertit en <modèle>/<link>/<capteur>.
SENSOR_FRAMES = {
    'tugbot/scan_front/scan_front': ('0.221', '0', '0.1404', '0'),
    'tugbot/scan_back/scan_back': ('-0.2075', '0', '0.205', '3.141592654'),
    'tugbot/scan_omni/scan_omni': ('-0.1855', '0', '0.5318', '0'),
    # Crochet en position repos (le joint gripper_joint peut pivoter)
    'tugbot/gripper/sensor_contact': ('-0.425', '0', '0.135', '3.141592654'),
    'tugbot/imu_link/imu': ('0.14', '0.02', '0.25', '-1.57'),
    'tugbot/camera_front/color': ('0.0553', '0.0325', '0.4448', '0'),
    'tugbot/camera_front/depth': ('0.0553', '0.0175', '0.4448', '0'),
    'tugbot/camera_back/color': ('-0.241', '-0.0325', '0.2428', '3.141592654'),
    'tugbot/camera_back/depth': ('-0.241', '-0.0175', '0.2428', '3.141592654'),
}


def generate_launch_description():
    pkg_share = get_package_share_directory('mobile_robot_gazebo')
    # Monde "Tugbot in Warehouse" du Quick Start de Gazebo ; le Tugbot y est
    # inclus via model://tugbot (models/tugbot), le reste vient de Fuel
    world_file = os.path.join(pkg_share, 'world', 'tugbot_warehouse.sdf')
    bridge_config = os.path.join(pkg_share, 'config', 'ros_gz_bridge.yaml')
    rviz_config = os.path.join(pkg_share, 'rviz', 'tugbot.rviz')

    rviz = LaunchConfiguration('rviz')
    use_sim_time = {'use_sim_time': True}

    # Permet à Gazebo de résoudre les URI model://
    set_resource_path = AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH', os.path.join(pkg_share, 'models'))

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')),
        launch_arguments={
            'gz_args': f'-r {world_file}',
            'on_exit_shutdown': 'true',
        }.items(),
    )

    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{'config_file': bridge_config}, use_sim_time],
        output='screen',
    )

    # Place odom (départ du robot) dans le monde pour afficher /ground_truth_pose
    # (repère world_demo) ; pose initiale du tugbot dans world/tugbot_warehouse.sdf
    world_to_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['--frame-id', 'world_demo', '--child-frame-id', 'odom',
                   '--x', '13.9', '--y', '-10.6'],
        parameters=[use_sim_time],
    )

    sensor_tfs = [
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='tf_' + frame.replace('/', '_'),
            arguments=['--frame-id', 'base_link', '--child-frame-id', frame,
                       '--x', x, '--y', y, '--z', z, '--yaw', yaw],
            parameters=[use_sim_time],
        )
        for frame, (x, y, z, yaw) in SENSOR_FRAMES.items()
    ]

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_config],
        parameters=[use_sim_time],
        condition=IfCondition(rviz),
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'rviz', default_value='true',
            description='Lance RViz2 avec tous les lidars et caméras'),
        set_resource_path,
        gazebo,
        bridge,
        world_to_odom,
        *sensor_tfs,
        rviz_node,
    ])
