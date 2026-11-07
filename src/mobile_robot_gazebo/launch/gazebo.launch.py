import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import AppendEnvironmentVariable, DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
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

    world_file = os.path.join(pkg_share, 'world', 'tugbot_warehouse.sdf')
    bridge_config = os.path.join(pkg_share, 'config', 'ros_gz_bridge.yaml')
    rviz_config = os.path.join(pkg_share, 'rviz', 'tugbot.rviz')
    map_file = os.path.join(pkg_share, 'config', 'maps', 'warehouse.yaml')

    ekf_filter_node_config = os.path.join(pkg_share, "config", "ekf_filter_node.yaml")
    controllers_config = os.path.join(pkg_share, 'config', 'tugbot_controllers.yaml')
    with open(os.path.join(pkg_share, 'urdf', 'tugbot_ros2_control.urdf')) as f:
        robot_description = f.read()

    rviz = LaunchConfiguration('rviz')
    use_sim_time = {'use_sim_time': True}

    set_resource_path = AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.path.join(pkg_share, 'models'))

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

    # Publie /robot_description, dont gz_ros2_control a besoin pour démarrer
    # le controller_manager, et les TF base_link -> roues
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description}, use_sim_time],
        output='screen',
    )

    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '--param-file', controllers_config],
        parameters=[use_sim_time],
    )

    # Écoute /cmd_vel (TwistStamped) et publie l'odométrie des roues sur
    # /wheel/odometry, sans TF (laissée à robot_localization)
    diff_drive_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['diff_drive_controller', '--param-file', controllers_config,
                   '--controller-ros-args', '-r ~/cmd_vel:=/cmd_vel',
                   '--controller-ros-args', '-r ~/odom:=/wheel/odometry'],
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

    # Scan 360° longue portée tiré du nuage du VLP-16 (/scan_omni/points ->
    # /scan_omni/scan), utilisé par slam_toolbox et AMCL
    pointcloud_to_laserscan = Node(
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        name='pointcloud_to_laserscan',
        parameters=[os.path.join(pkg_share, 'config', 'pointcloud_to_laserscan.yaml')],
        remappings=[('cloud_in', '/scan_omni/points'), ('scan', '/scan_omni/scan')],
        output='screen',
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', LaunchConfiguration('rviz_config')],
        parameters=[use_sim_time],
        condition=IfCondition(rviz),
        output='screen',
    )

    ekf_filter_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[ekf_filter_node_config, use_sim_time],
    )


    # Vérité terrain (world_demo) rattachée à map, à la pose de départ du robot
    # (world/tugbot_warehouse.sdf) : map a pour origine le départ du robot
    world_to_map = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['--frame-id', 'world_demo', '--child-frame-id', 'map',
                   '--x', '13.9', '--y', '-10.6'],
        parameters=[use_sim_time],
    )

    # map -> odom identité tant qu'aucune localisation (slam_toolbox, AMCL) ne la publie
    map_to_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['--frame-id', 'map', '--child-frame-id', 'odom'],
        parameters=[use_sim_time],
        condition=IfCondition(LaunchConfiguration('publish_map_odom')),
    )

    # Carte sauvegardée (slam.launch.py + map_saver_cli) publiée sur /map ;
    # désactivée si map:='' (slam_toolbox publie alors /map lui-même)
    load_map = IfCondition(PythonExpression(["'", LaunchConfiguration('map'), "' != ''"]))

    map_server = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        parameters=[{'yaml_filename': LaunchConfiguration('map')}, use_sim_time],
        condition=load_map,
        output='screen',
    )

    # map_server est un nœud lifecycle : le configure puis l'active au démarrage
    map_lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_map',
        parameters=[{'node_names': ['map_server'], 'autostart': True}, use_sim_time],
        condition=load_map,
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument('rviz', default_value='true', description='Lance RViz2 avec tous les lidars et caméras'),
        DeclareLaunchArgument('publish_map_odom', default_value='true', description='Publie map -> odom (identité) ; false si slam_toolbox ou AMCL la publie'),
        DeclareLaunchArgument('rviz_config', default_value=rviz_config, description='Configuration RViz2'),
        DeclareLaunchArgument('map', default_value=map_file, description="Carte à publier sur /map ('' pour aucune)"),
        set_resource_path,
        gazebo, rviz_node,
        bridge,
        world_to_map,
        map_to_odom,
        map_server,
        map_lifecycle_manager,
        robot_state_publisher,
        joint_state_broadcaster_spawner,
        diff_drive_spawner,
        *sensor_tfs,
        pointcloud_to_laserscan,

        ekf_filter_node
    ])
