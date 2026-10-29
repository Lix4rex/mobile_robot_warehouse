cmake_minimum_required(VERSION 3.8)
project(mobile_robot_gazebo)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY launch models world config rviz
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
