from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'cmd_vel_topic', default_value='/cmd_vel',
            description='Topic TwistStamped écouté par le diff_drive_controller'),
        DeclareLaunchArgument(
            'use_sim_time', default_value='true',
            description='Horodate les commandes avec le temps de la simulation'),

        # Fenêtre de téléopération : boutons, flèches ou ZQSD
        Node(
            package='mobile_robot_teleop',
            executable='teleop_gui',
            parameters=[{
                'cmd_vel_topic': LaunchConfiguration('cmd_vel_topic'),
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            }],
            output='screen',
        ),
    ])
