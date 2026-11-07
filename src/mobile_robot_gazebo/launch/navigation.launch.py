import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

# Nœuds lifecycle de la navigation, démarrés dans cet ordre par le lifecycle_manager.
# route_server et docking_server (lancés par nav2_bringup) ne sont pas utilisés ici
LIFECYCLE_NODES = [
    'controller_server',
    'smoother_server',
    'planner_server',
    'behavior_server',
    'velocity_smoother',
    'collision_monitor',
    'bt_navigator',
    'waypoint_follower',
]


def generate_launch_description():
    pkg_share = get_package_share_directory('mobile_robot_gazebo')
    nav2_params = os.path.join(pkg_share, 'config', 'nav2_params.yaml')

    # Simulation + carte + AMCL (map -> odom), sans la téléop : elle publie en
    # continu sur /cmd_vel et écraserait les commandes de Nav2
    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, 'launch', 'localization.launch.py')),
        launch_arguments={
            'map': LaunchConfiguration('map'),
            'teleop': 'false',
            'rviz_config': os.path.join(pkg_share, 'rviz', 'navigation.rviz'),
        }.items(),
    )

    def nav2_node(package, executable, remappings=()):
        return Node(
            package=package,
            executable=executable,
            name=executable,
            parameters=[nav2_params],
            remappings=list(remappings),
            output='screen',
        )

    # Chaîne de commande : controller_server / behavior_server -> cmd_vel_nav
    # -> velocity_smoother -> cmd_vel_smoothed -> collision_monitor -> /cmd_vel
    nav2_nodes = [
        nav2_node('nav2_controller', 'controller_server', [('cmd_vel', 'cmd_vel_nav')]),
        nav2_node('nav2_smoother', 'smoother_server'),
        nav2_node('nav2_planner', 'planner_server'),
        nav2_node('nav2_behaviors', 'behavior_server', [('cmd_vel', 'cmd_vel_nav')]),
        nav2_node('nav2_velocity_smoother', 'velocity_smoother', [('cmd_vel', 'cmd_vel_nav')]),
        nav2_node('nav2_collision_monitor', 'collision_monitor'),
        nav2_node('nav2_bt_navigator', 'bt_navigator'),
        nav2_node('nav2_waypoint_follower', 'waypoint_follower'),
    ]

    navigation_lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        parameters=[{'node_names': LIFECYCLE_NODES, 'autostart': True, 'use_sim_time': True}],
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'map', default_value=os.path.join(pkg_share, 'config', 'maps', 'warehouse.yaml'),
            description='Carte sur laquelle naviguer'),
        localization,
        *nav2_nodes,
        navigation_lifecycle_manager,
    ])
