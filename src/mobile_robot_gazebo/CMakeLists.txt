cmake_minimum_required(VERSION 3.8)
project(mobile_robot_gazebo)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY launch world config rviz urdf
  DESTINATION share/${PROJECT_NAME}
)

# gz_ros2_control n'accepte qu'un chemin absolu pour son fichier de paramètres :
# model.sdf est installé après substitution de @CONTROLLERS_CONFIG@
install(
  DIRECTORY models
  DESTINATION share/${PROJECT_NAME}
  PATTERN "model.sdf" EXCLUDE
)
set(CONTROLLERS_CONFIG
  ${CMAKE_INSTALL_PREFIX}/share/${PROJECT_NAME}/config/tugbot_controllers.yaml)
configure_file(models/tugbot/model.sdf ${CMAKE_CURRENT_BINARY_DIR}/model.sdf @ONLY)
install(
  FILES ${CMAKE_CURRENT_BINARY_DIR}/model.sdf
  DESTINATION share/${PROJECT_NAME}/models/tugbot
)

ament_package()
