import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    pkg_share = get_package_share_directory('mobile_robot_gazebo')

    # Simulation + EKF (odom -> base_link), sans la TF map -> odom statique ni
    # la carte sauvegardée : c'est slam_toolbox qui les publie
    simulation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, 'launch', 'gazebo.launch.py')),
        launch_arguments={
            'publish_map_odom': 'false',
            'map': '',  # /map est publiée par slam_toolbox
            'rviz_config': os.path.join(pkg_share, 'rviz', 'slam.rviz'),
        }.items(),
    )

    # Cartographie en ligne à partir de /scan_omni/scan : publie /map et map -> odom
    slam_toolbox = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('slam_toolbox'), 'launch', 'online_async_launch.py')),
        launch_arguments={
            'slam_params_file': os.path.join(pkg_share, 'config', 'slam_toolbox.yaml'),
            'use_sim_time': 'true',
        }.items(),
    )

    # Fenêtre de téléopération pour parcourir l'entrepôt pendant la cartographie
    teleop = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('mobile_robot_teleop'), 'launch', 'teleop.launch.py')),
        condition=IfCondition(LaunchConfiguration('teleop')),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'teleop', default_value='true',
            description='Ouvre la fenêtre de téléopération'),
        simulation,
        slam_toolbox,
        teleop,
    ])
