"""Fenêtre de téléopération : publie un TwistStamped sur /cmd_vel.

Le robot ne bouge que tant qu'un bouton ou une touche est maintenu.
Les commandes sont publiées en continu (zéros compris), ce qui évite au
diff_drive_controller de déclencher son cmd_vel_timeout tant que la fenêtre est ouverte.
"""
import tkinter as tk
from tkinter import ttk

from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.node import Node

# Direction -> (signe de la vitesse linéaire, signe de la vitesse angulaire)
DIRECTIONS = {
    'forward_left': (1, 1), 'forward': (1, 0), 'forward_right': (1, -1),
    'left': (0, 1), 'right': (0, -1),
    'backward_left': (-1, -1), 'backward': (-1, 0), 'backward_right': (-1, 1),
}

# Disposition du pavé de boutons : (direction, libellé, ligne, colonne)
BUTTONS = [
    ('forward_left', '↖', 0, 0), ('forward', '↑', 0, 1), ('forward_right', '↗', 0, 2),
    ('left', '↺', 1, 0), ('right', '↻', 1, 2),
    ('backward_left', '↙', 2, 0), ('backward', '↓', 2, 1), ('backward_right', '↘', 2, 2),
]

# Touches (keysym) -> direction ; flèches, ZQSD (AZERTY) et WASD (QWERTY)
KEYS = {
    'Up': 'forward', 'z': 'forward', 'w': 'forward',
    'Down': 'backward', 's': 'backward',
    'Left': 'left', 'q': 'left', 'a': 'left',
    'Right': 'right', 'd': 'right',
}

# Délai avant de prendre en compte un relâchement de touche : l'auto-répétition
# du clavier génère des paires relâchement/appui qu'il faut ignorer
KEY_RELEASE_DELAY_MS = 60


class TeleopGui(Node):

    def __init__(self):
        super().__init__('teleop_gui')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('frame_id', 'base_link')
        self.declare_parameter('publish_rate', 20.0)
        # Limites du diff_drive_controller (config/tugbot_controllers.yaml)
        self.declare_parameter('max_linear_speed', 1.0)
        self.declare_parameter('max_angular_speed', 1.5)
        self.declare_parameter('linear_speed', 0.3)
        self.declare_parameter('angular_speed', 0.6)

        topic = self.get_parameter('cmd_vel_topic').value
        self.frame_id = self.get_parameter('frame_id').value
        self.period_ms = int(1000.0 / self.get_parameter('publish_rate').value)
        max_linear = self.get_parameter('max_linear_speed').value
        max_angular = self.get_parameter('max_angular_speed').value

        self.publisher = self.create_publisher(TwistStamped, topic, 10)

        # Sources actives : ('button', direction) ou ('key', keysym)
        self.active = set()
        self.pending_releases = {}

        self.root = tk.Tk()
        self.root.title('Téléopération Tugbot')
        self.root.resizable(False, False)
        self.root.protocol('WM_DELETE_WINDOW', self.close)

        self.linear_speed = tk.DoubleVar(value=self.get_parameter('linear_speed').value)
        self.angular_speed = tk.DoubleVar(value=self.get_parameter('angular_speed').value)
        self.status = tk.StringVar()

        self.build_ui(topic, max_linear, max_angular)

        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)
        # Sécurité : arrêt si la fenêtre perd le focus avec une touche enfoncée
        self.root.bind('<FocusOut>', lambda _: self.release_keys())

        self.get_logger().info(f'Téléopération sur {topic}')

    def build_ui(self, topic, max_linear, max_angular):
        frame = ttk.Frame(self.root, padding=12)
        frame.grid()

        pad = ttk.Frame(frame)
        pad.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        style = ttk.Style()
        style.configure('Pad.TButton', font=('TkDefaultFont', 20), width=3)
        style.configure('Stop.TButton', font=('TkDefaultFont', 20, 'bold'),
                        width=3, foreground='#c0392b')

        for direction, label, row, col in BUTTONS:
            button = ttk.Button(pad, text=label, style='Pad.TButton')
            button.grid(row=row, column=col, padx=3, pady=3, ipady=8)
            source = ('button', direction)
            button.bind('<ButtonPress-1>', lambda _, s=source: self.active.add(s))
            button.bind('<ButtonRelease-1>', lambda _, s=source: self.active.discard(s))

        stop = ttk.Button(pad, text='■', style='Stop.TButton', command=self.stop)
        stop.grid(row=1, column=1, padx=3, pady=3, ipady=8)

        ttk.Label(frame, text='Vitesse linéaire (m/s)').grid(row=1, column=0, sticky='w')
        tk.Scale(frame, variable=self.linear_speed, from_=0.05, to=max_linear,
                 resolution=0.05, orient='horizontal', length=200,
                 takefocus=0).grid(row=1, column=1)
        ttk.Label(frame, text='Vitesse angulaire (rad/s)').grid(row=2, column=0, sticky='w')
        tk.Scale(frame, variable=self.angular_speed, from_=0.05, to=max_angular,
                 resolution=0.05, orient='horizontal', length=200,
                 takefocus=0).grid(row=2, column=1)

        ttk.Label(frame, textvariable=self.status, font=('TkFixedFont', 10)).grid(
            row=3, column=0, columnspan=2, pady=(10, 4))
        ttk.Label(
            frame, foreground='#666', justify='center',
            text=f'Maintenir un bouton, les flèches ou ZQSD · Espace : stop\n{topic}',
        ).grid(row=4, column=0, columnspan=2)

    def on_key_press(self, event):
        key = event.keysym if event.keysym in KEYS else event.keysym.lower()
        if key == 'space':
            self.stop()
            return
        if key not in KEYS:
            return
        pending = self.pending_releases.pop(key, None)
        if pending is not None:
            self.root.after_cancel(pending)
        self.active.add(('key', key))

    def on_key_release(self, event):
        key = event.keysym if event.keysym in KEYS else event.keysym.lower()
        if key not in KEYS:
            return
        self.pending_releases[key] = self.root.after(
            KEY_RELEASE_DELAY_MS, self.release_key, key)

    def release_key(self, key):
        self.pending_releases.pop(key, None)
        self.active.discard(('key', key))

    def release_keys(self):
        self.active = {s for s in self.active if s[0] != 'key'}

    def stop(self):
        self.active.clear()

    def command(self):
        """Somme des directions actives, bornée à ±1 sur chaque axe."""
        linear, angular = 0, 0
        for kind, name in self.active:
            sign_linear, sign_angular = DIRECTIONS[KEYS[name] if kind == 'key' else name]
            linear += sign_linear
            angular += sign_angular
        linear = max(-1, min(1, linear))
        angular = max(-1, min(1, angular))
        return linear * self.linear_speed.get(), angular * self.angular_speed.get()

    def publish(self, linear, angular):
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        msg.twist.linear.x = linear
        msg.twist.angular.z = angular
        self.publisher.publish(msg)

    def tick(self):
        if not rclpy.ok():
            self.close()
            return
        rclpy.spin_once(self, timeout_sec=0.0)
        linear, angular = self.command()
        self.publish(linear, angular)
        self.status.set(f'v = {linear:+.2f} m/s   ω = {angular:+.2f} rad/s')
        self.root.after(self.period_ms, self.tick)

    def close(self):
        if rclpy.ok():
            self.publish(0.0, 0.0)
        self.root.quit()

    def run(self):
        self.root.after(0, self.tick)
        self.root.mainloop()
        self.root.destroy()


def main():
    rclpy.init()
    node = TeleopGui()
    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
