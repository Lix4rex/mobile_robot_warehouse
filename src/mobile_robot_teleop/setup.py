from glob import glob

from setuptools import find_packages, setup

package_name = 'mobile_robot_teleop'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Lix4rex',
    maintainer_email='axelparis6@gmail.com',
    description='Interface graphique de téléopération du Tugbot (TwistStamped sur /cmd_vel)',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'teleop_gui = mobile_robot_teleop.teleop_gui:main',
        ],
    },
)
