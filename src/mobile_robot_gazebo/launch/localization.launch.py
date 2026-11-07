import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('mobile_robot_gazebo')
    use_sim_time = {'use_sim_time': True}

    # Simulation + EKF (odom -> base_link) + carte sauvegardée sur /map, sans la
    # TF map -> odom statique : c'est AMCL qui la publie
    simulation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, 'launch', 'gazebo.launch.py')),
        launch_arguments={
            'publish_map_odom': 'false',
            'map': LaunchConfiguration('map'),
        }.items(),
    )

    # Recale /scan_omni/scan sur la carte : publie map -> odom et /amcl_pose
    amcl = Node(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        parameters=[os.path.join(pkg_share, 'config', 'amcl.yaml')],
        output='screen',
    )

    # amcl est un nœud lifecycle : le configure puis l'active au démarrage
    localization_lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_localization',
        parameters=[{'node_names': ['amcl'], 'autostart': True}, use_sim_time],
        output='screen',
    )

    # Fenêtre de téléopération pour tester la localisation en roulant
    teleop = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('mobile_robot_teleop'), 'launch', 'teleop.launch.py')),
        condition=IfCondition(LaunchConfiguration('teleop')),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'map', default_value=os.path.join(pkg_share, 'config', 'maps', 'warehouse.yaml'),
            description='Carte sur laquelle se localiser'),
        DeclareLaunchArgument(
            'teleop', default_value='true',
            description='Ouvre la fenêtre de téléopération'),
        simulation,
        amcl,
        localization_lifecycle_manager,
        teleop,
    ])
