"""
Haptic Steering Game -- Driver's Seat Edition
==============================================
You're sitting in the car. There's no sprite to look at -- the road
itself is rendered in perspective (like classic Out Run-style racers),
and steering the Hapkit's handle shifts YOUR viewpoint within the lane.

The Hapkit motor pushes back on your hand the whole time:
  - It self-centers, like real power steering (stiffer at higher speed).
  - It gives a physical tug in the direction the road is about to bend,
    so a good driver can "feel" the next curve coming.
  - Drift near the edge of the road -> the wheel buzzes (rumble strip).
  - Drive off the road entirely -> the wheel gets heavy and sluggish.
  - Hit an obstacle -> a sharp jolt, and the screen flashes red.

Run this with the Arduino sketch (main.cpp) loaded and the
Hapkit set to CAR_GAME mode (send '7' over serial, or leave it as the
default mode -- it already is in the provided sketch).

No Hapkit plugged in? The game still runs with arrow-key steering, so
you (or campers) can build/test the game logic before hardware is ready.
"""

import sys
import math
import random
import time
import threading
import pygame
import serial.tools.list_ports
from haplink import Haplink, DataType


# =====================================================================
# TUNABLE CONSTANTS -- change these! Great spot for campers to experiment
# =====================================================================

BAUD_RATE = 115200

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# ---- perspective / camera ----
HORIZON_ROW = 230              # screen row where the horizon sits (sky above, road below)
CAMERA_HEIGHT = 550            # world units -- how "high up" the driver's eyes are (lower = bigger/closer look)
FIELD_OF_VIEW_DEG = 100        # bigger = wider/fisheye-ier view
CAMERA_DEPTH = 1.0 / math.tan(math.radians(FIELD_OF_VIEW_DEG / 2))
NEAR_CLIP = 40                 # world units, closest distance we ever render (avoids blow-ups)
DRAW_DISTANCE = 24000          # world units ahead rendered before fading into the horizon

# ---- road ----
LANE_HALF_WIDTH = 2200         # world units, half the width of the drivable road (narrowed from 6000 for realism)
ROAD_CURVE_AMPLITUDE_1 = 5000  # world units, big slow curves (increased from 1800)
ROAD_CURVE_FREQ_1 = 0.00015    # frequency (sweeping curves)
ROAD_CURVE_AMPLITUDE_2 = 1200  # world units, smaller/faster wiggle layered on top (increased from 600)
ROAD_CURVE_FREQ_2 = 0.0004     # frequency
RUMBLE_STRIPE_LENGTH = 400     # world units per rumble-strip color band
DASH_LENGTH = 500              # world units per center-line dash
SEGMENT_LENGTH = 150.0         # world units per road segment (optimizes drawing performance)

# ---- steering feel & physics ----
STEERING_SENSITIVITY = 1200.0  # world units/sec lateral speed per cm of handle displacement (increased from 600)
LOOKAHEAD_DISTANCE = 2400      # world units "ahead" used to compute road_pull (curve feel)
PULL_SCALE = 0.8               # converts road slope into a -1..1 road_pull value (adjusted for new curves)

# ---- speed / difficulty ----
START_SPEED = 1800             # world units/sec, initial forward speed
MAX_SPEED = 5200               # world units/sec, top forward speed
SPEED_RAMP_TIME = 60           # seconds to go from START_SPEED to MAX_SPEED

# ---- obstacles ----
OBSTACLE_SPAWN_EVERY = 8000    # world units of travel between obstacle spawns
OBSTACLE_WORLD_WIDTH = 700
OBSTACLE_WORLD_HEIGHT = 900
CAR_HALF_WIDTH_WORLD = 150     # used only for collision math -- no sprite is drawn
COLLISION_Z_WINDOW = 220       # world units of forward "depth" counted as a hit
STARTING_LIVES = 3
CRASH_FREEZE_TIME = 0.35       # seconds the world "freezes" after a crash (lets the jolt play)


# =====================================================================
# Road shape: a smooth, endless curving path defined as a function of
# "world distance traveled" (z). Two sine waves summed together gives
# gentle S-curves without needing to store a giant lookup table.
# =====================================================================

_phase_1 = random.uniform(0, 2 * math.pi)
_phase_2 = random.uniform(0, 2 * math.pi)


def road_center(world_z):
    """World-space x coordinate of the center of the road at a given world_z (distance)."""
    return (ROAD_CURVE_AMPLITUDE_1 * math.sin(world_z * ROAD_CURVE_FREQ_1 + _phase_1)
            + ROAD_CURVE_AMPLITUDE_2 * math.sin(world_z * ROAD_CURVE_FREQ_2 + _phase_2))


def project_x(world_x, camera_x, scale):
    """Project a world x-coordinate to a screen x-coordinate given a perspective scale."""
    return SCREEN_WIDTH / 2 + scale * (world_x - camera_x) * (SCREEN_WIDTH / 2)


def find_hapkit_port():
    """Auto-detects active serial ports matching standard Arduino/USB-serial descriptions."""
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = p.description.lower()
        if "ch340" in desc or "arduino" in desc or "usb-serial" in desc or "usb serial" in desc:
            return p.device
    if ports:
        return ports[0].device
    return None


# =====================================================================
# Haplink connection wrapper (runs updates in a background thread
# for extremely smooth haptic forces regardless of Pygame frame drops)
# =====================================================================

class HapticLink:
    def __init__(self):
        self.connected = False
        self.link = None
        self.sim_handle_pos = 0.0   # used only in keyboard fallback mode
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

        self.handle_pos = 0.0
        self.handle_vel = 0.0
        self.road_pull = 0.0
        self.surface_state = 0
        self.game_speed = 0.0

        port = find_hapkit_port()
        if port:
            try:
                self.link = Haplink(port, baudrate=BAUD_RATE)
                self.link.connect()
                self.link.register_param(1, 'road_pull', DataType.FLOAT)
                self.link.register_param(2, 'surface_state', DataType.INT16)
                self.link.register_param(3, 'game_speed', DataType.FLOAT)
                self.link.register_telemetry(0, 'handle_pos', DataType.FLOAT)
                self.link.register_telemetry(1, 'handle_vel', DataType.FLOAT)
                self.connected = True
                print(f"Connected to Hapkit on {port}")

                # Spawn update thread
                self.running = True
                self.thread = threading.Thread(target=self._update_loop, daemon=True)
                self.thread.start()
            except Exception as e:
                print(f"Could not connect to Hapkit ({e}). Using arrow keys instead.")
        else:
            print("No Hapkit detected via auto-port scan. Using arrow keys instead.")

    def _update_loop(self):
        while self.running:
            with self.lock:
                # Push latest parameter changes to link
                self.link.set_param('road_pull', self.road_pull)
                self.link.set_param('surface_state', self.surface_state)
                self.link.set_param('game_speed', self.game_speed)

                # Tick the serial protocol
                self.link.update()

                # Pull latest telemetry values
                pos = self.link.get_telemetry('handle_pos')
                vel = self.link.get_telemetry('handle_vel')
                if pos is not None:
                    self.handle_pos = -1.0 * pos
                if vel is not None:
                    self.handle_vel = vel
            time.sleep(0.005)  # 200 Hz update loop

    def update_and_read(self, keys_pressed, dt):
        """Returns (handle_pos_cm, handle_vel_cms)."""
        if self.connected:
            with self.lock:
                return self.handle_pos, self.handle_vel
        else:
            # keyboard fallback: arrow keys nudge a simulated handle position,
            # with a simple spring pulling it back toward center
            move_speed = 12.0   # cm/sec when a key is held
            center_pull = 3.0   # cm/sec^2-ish, pulls back toward 0 when no key held
            if keys_pressed[pygame.K_LEFT]:
                self.sim_handle_pos -= move_speed * dt
            elif keys_pressed[pygame.K_RIGHT]:
                self.sim_handle_pos += move_speed * dt
            else:
                self.sim_handle_pos -= self.sim_handle_pos * min(1.0, center_pull * dt)
            self.sim_handle_pos = max(-6.0, min(6.0, self.sim_handle_pos))
            return self.sim_handle_pos, 0.0

    def send_forces(self, road_pull, surface_state, game_speed):
        if self.connected:
            with self.lock:
                self.road_pull = road_pull
                self.surface_state = surface_state
                self.game_speed = game_speed

    def close(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.connected and self.link:
            with self.lock:
                try:
                    self.link.disconnect()
                except Exception:
                    pass


# =====================================================================
# Obstacle & Decoration Classes
# =====================================================================

class Obstacle:
    def __init__(self, world_z):
        self.world_z = world_z
        # spawn somewhere across the road, sometimes near the edges
        max_offset = LANE_HALF_WIDTH - OBSTACLE_WORLD_WIDTH / 2
        lateral = random.uniform(-max_offset, max_offset)
        self.world_x = road_center(world_z) + lateral
        self.hit_checked = False


# =====================================================================
# Visual Helper Functions
# =====================================================================

def draw_sky_gradient(screen):
    """Draws a beautiful sunset sky gradient above the horizon."""
    # Drawn slightly lower than HORIZON_ROW to cover vertical screen shake
    for y in range(HORIZON_ROW + 20):
        t = y / (HORIZON_ROW + 20)
        r = int(18 + t * 90)
        g = int(25 + t * 110)
        b = int(60 + t * 140)
        pygame.draw.line(screen, (r, g, b), (0, y), (SCREEN_WIDTH, y))


def draw_sun_and_mountains(screen, sky_offset):
    """Draws a parallax-scrolling sun and multi-layered mountain silhouette."""
    # 1. Glowing Sunset Sun
    sun_x = (SCREEN_WIDTH / 2 - sky_offset * 0.15) % (SCREEN_WIDTH + 200) - 100
    sun_y = HORIZON_ROW - 20
    for r in range(45, 0, -5):
        alpha = int(110 * (1.0 - r / 45.0))
        sun_glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(sun_glow, (255, 110, 30, alpha), (r, r), r)
        screen.blit(sun_glow, (sun_x - r, sun_y - r))
        
    # 2. Far mountains (dark blue-purple shade)
    far_color = (30, 36, 64)
    pts_far = []
    for px in range(0, SCREEN_WIDTH + 80, 80):
        hx = px + sky_offset * 0.4
        h = 35 + math.sin(hx * 0.008) * 22 + math.cos(hx * 0.02) * 10
        pts_far.append((px, HORIZON_ROW - h))
    pts_far.insert(0, (0, HORIZON_ROW))
    pts_far.append((SCREEN_WIDTH, HORIZON_ROW))
    pygame.draw.polygon(screen, far_color, pts_far)
    
    # 3. Near mountains (even darker silhouette layer)
    near_color = (18, 22, 40)
    pts_near = []
    for px in range(0, SCREEN_WIDTH + 60, 60):
        hx = px + sky_offset
        h = 16 + math.sin(hx * 0.016) * 16 + math.cos(hx * 0.038) * 8
        pts_near.append((px, HORIZON_ROW - h))
    pts_near.insert(0, (0, HORIZON_ROW))
    pts_near.append((SCREEN_WIDTH, HORIZON_ROW))
    pygame.draw.polygon(screen, near_color, pts_near)


def draw_obstacle(screen, x, y, w, h, scale):
    """Draws a gorgeous pseudo-3D construction barrier warning sign."""
    # 1. Draw Legs
    leg_w = max(2.0, 16.0 * scale)
    pygame.draw.rect(screen, (50, 50, 50), (x - w * 0.3 - leg_w / 2, y - h, leg_w, h))
    pygame.draw.rect(screen, (50, 50, 50), (x + w * 0.3 - leg_w / 2, y - h, leg_w, h))

    # 2. Outer board (orange)
    board_h = h * 0.4
    board_y = y - h
    pygame.draw.rect(screen, (240, 100, 20), (x - w / 2, board_y, w, board_h), border_radius=int(max(1, 4 * scale)))

    # 3. White diagonal stripes
    stripe_w = w / 5.0
    for s in range(5):
        if s % 2 == 1:
            pts = [
                (x - w / 2 + s * stripe_w, board_y),
                (x - w / 2 + (s + 1) * stripe_w, board_y),
                (x - w / 2 + (s + 0.5) * stripe_w, board_y + board_h),
                (x - w / 2 + (s - 0.5) * stripe_w, board_y + board_h)
            ]
            # Clamp points to the board's bounds
            pts = [(max(x - w / 2, min(x + w / 2, px)), py) for px, py in pts]
            pygame.draw.polygon(screen, (240, 240, 240), pts)

    # 4. Warning lights
    light_r = max(4.0, 18.0 * scale)
    pygame.draw.circle(screen, (255, 220, 0), (int(x - w * 0.35), int(board_y)), int(light_r))
    pygame.draw.circle(screen, (255, 220, 0), (int(x + w * 0.35), int(board_y)), int(light_r))
    pygame.draw.circle(screen, (0, 0, 0), (int(x - w * 0.35), int(board_y)), int(light_r), width=2)
    pygame.draw.circle(screen, (0, 0, 0), (int(x + w * 0.35), int(board_y)), int(light_r), width=2)


def draw_tree(screen, x, y, w, h, scale):
    """Draws a beautiful stylized layered roadside pine tree."""
    # 1. Trunk
    trunk_w = max(2.0, 28.0 * scale)
    trunk_h = h * 0.28
    pygame.draw.rect(screen, (90, 55, 35), (x - trunk_w / 2, y - trunk_h, trunk_w, trunk_h))
    
    # 2. Green leaves (3 stacked triangles)
    leaf_y = y - trunk_h
    leaf_h = h * 0.33
    leaf_w = w
    for layer in range(3):
        layer_y = leaf_y - layer * (leaf_h * 0.55)
        layer_w = leaf_w * (1.0 - layer * 0.25)
        # Shift leaves slightly color-wise for depth
        color = (25, 80 + layer * 20, 40)
        pts = [
            (x, layer_y - leaf_h),
            (x - layer_w / 2, layer_y),
            (x + layer_w / 2, layer_y)
        ]
        pygame.draw.polygon(screen, color, pts)


def draw_hud(screen, font, state):
    """Draws a neat modern stats panel containing distance, speed, and lives."""
    # Semi-transparent backing panel
    panel = pygame.Surface((220, 110), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 140))
    screen.blit(panel, (15, 15))

    dist_text = font.render(f"DISTANCE: {int(state['car_world_z'] / 10):,} m", True, (255, 255, 255))
    speed_text = font.render(f"SPEED: {int(state['speed'] / 10)} km/h", True, (255, 255, 255))
    lives_text = font.render("LIVES:", True, (255, 255, 255))

    screen.blit(dist_text, (25, 25))
    screen.blit(speed_text, (25, 53))
    screen.blit(lives_text, (25, 81))

    # Lives indicators (heart-like glowing circles)
    for l in range(state['lives']):
        lx = 100 + l * 22
        ly = 90
        pygame.draw.circle(screen, (255, 55, 55), (lx, ly), 7)
        pygame.draw.circle(screen, (255, 200, 200), (lx - 2, ly - 2), 2)


# =====================================================================
# Main game
# =====================================================================

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Haptic Highway -- Driver's Seat")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Calibri", 20, bold=True)
    big_font = pygame.font.SysFont("Calibri", 54, bold=True)

    haptics = HapticLink()

    new_game_state = {
            'car_world_z': 0.0,
            'car_x': road_center(0.0),  # starts at the road center
            'speed': START_SPEED,
            'elapsed': 0.0,
            'lives': STARTING_LIVES,
            'obstacles': [Obstacle(2000 + i * OBSTACLE_SPAWN_EVERY) for i in range(6)],
            'next_spawn_z': 2000 + 6 * OBSTACLE_SPAWN_EVERY,
            'crash_freeze': 0.0,
            'game_over': False,
            'sky_offset': 0.0,          # horizontal scroll offset for mountains/sun parallax
        }

    state = new_game_state

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r and state['game_over']:
                    state = new_game_state
                if event.key == pygame.K_ESCAPE:
                    running = False

        keys = pygame.key.get_pressed()

        # ---- read the handle (real hardware or keyboard fallback) ----
        handle_pos, handle_vel = haptics.update_and_read(keys, dt)

        # ---- camera/world vibration shake ----
        shake_x = 0
        shake_y = 0

        if not state['game_over']:
            # ---- advance the world ----
            if state['crash_freeze'] > 0:
                state['crash_freeze'] -= dt
                surface_state = 3
                camera_x = state['car_x']
                
                # Heavy crash shake
                shake_x = random.randint(-12, 12)
                shake_y = random.randint(-12, 12)
            else:
                state['elapsed'] += dt
                
                # Determine target speed limit (ramps up over time)
                target_max = START_SPEED + (MAX_SPEED - START_SPEED) * min(1.0, state['elapsed'] / SPEED_RAMP_TIME)

                # Figure out road / rumble / off-road state using car's world lateral position
                offset_from_center = state['car_x'] - road_center(state['car_world_z'])
                if abs(offset_from_center) < LANE_HALF_WIDTH * 0.75:
                    surface_state = 0
                elif abs(offset_from_center) < LANE_HALF_WIDTH:
                    surface_state = 1  # rumble strip
                else:
                    surface_state = 2  # off-road

                # Adjust target speed based on surface state
                if surface_state == 2:
                    target_speed = START_SPEED * 0.5  # Slow down off-road
                    
                    # Off-road rumble vibration camera shake
                    shake_factor = int(state['speed'] / START_SPEED * 4)
                    if shake_factor > 0:
                        shake_x = random.randint(-shake_factor, shake_factor)
                        shake_y = random.randint(-shake_factor, shake_factor)
                else:
                    target_speed = target_max
                    # High-speed subtle visual vibration
                    if state['speed'] > MAX_SPEED * 0.85:
                        shake_x = random.randint(-1, 1)
                        shake_y = random.randint(-1, 1)

                # Smoothly adjust speed towards target
                if state['speed'] < target_speed:
                    state['speed'] = min(target_speed, state['speed'] + 2000.0 * dt)
                elif state['speed'] > target_speed:
                    state['speed'] = max(target_speed, state['speed'] - 4000.0 * dt)

                # Move forward
                state['car_world_z'] += state['speed'] * dt

                # Steering changes the car's actual lateral position (differential physics)
                # Max steering speed is STEERING_SENSITIVITY * handle_pos
                lateral_velocity = handle_pos * STEERING_SENSITIVITY
                state['car_x'] += lateral_velocity * (state['speed'] / START_SPEED) * dt

                # Clamp lateral position relative to road center to prevent flying away off-road
                curr_road_center = road_center(state['car_world_z'])
                max_offset = LANE_HALF_WIDTH * 2.0
                if state['car_x'] - curr_road_center > max_offset:
                    state['car_x'] = curr_road_center + max_offset
                elif state['car_x'] - curr_road_center < -max_offset:
                    state['car_x'] = curr_road_center - max_offset

                # Scroll sky offset based on road bends and steering velocity
                road_bend = road_center(state['car_world_z'] + 100) - road_center(state['car_world_z'])
                state['sky_offset'] = (state['sky_offset'] - (handle_pos * 1.5 + road_bend * 0.08)) % SCREEN_WIDTH

                camera_x = state['car_x']

            car_world_z = state['car_world_z']

            # ---- spawn new obstacles as the road unwinds ----
            while state['next_spawn_z'] < car_world_z + DRAW_DISTANCE:
                state['obstacles'].append(Obstacle(state['next_spawn_z']))
                state['next_spawn_z'] += OBSTACLE_SPAWN_EVERY

            # drop obstacles well behind the car
            state['obstacles'] = [o for o in state['obstacles'] if o.world_z > car_world_z - 500]

            # ---- collision check ----
            crashed_this_frame = False
            if state['crash_freeze'] <= 0:
                for obstacle in state['obstacles']:
                    if obstacle.hit_checked:
                        continue
                    if abs(obstacle.world_z - car_world_z) < COLLISION_Z_WINDOW:
                        obstacle.hit_checked = True
                        if abs(obstacle.world_x - camera_x) < (OBSTACLE_WORLD_WIDTH / 2 + CAR_HALF_WIDTH_WORLD):
                            crashed_this_frame = True

            if crashed_this_frame:
                state['lives'] -= 1
                state['crash_freeze'] = CRASH_FREEZE_TIME
                surface_state = 3
                if state['lives'] <= 0:
                    state['game_over'] = True

            # ---- compute the haptic "road pull" (feel the curve ahead) ----
            slope = (road_center(car_world_z + LOOKAHEAD_DISTANCE) - road_center(car_world_z)) / LOOKAHEAD_DISTANCE
            road_pull = max(-1.0, min(1.0, slope * PULL_SCALE))
            game_speed_norm = max(0.0, min(1.0, (state['speed'] - START_SPEED) / (MAX_SPEED - START_SPEED)))

            haptics.send_forces(road_pull, surface_state, game_speed_norm)
        else:
            car_world_z = state['car_world_z']
            camera_x = state['car_x']
            haptics.send_forces(0.0, 0, 0.0)

        # =================================================================
        # DRAW -- Perspective segment-based road rendering
        # =================================================================
        # 1. Sky Gradient
        draw_sky_gradient(screen)

        # 2. Sunset Sun and Parallax Mountains
        draw_sun_and_mountains(screen, state['sky_offset'])

        # 3. Draw fallback grass background (just in case)
        pygame.draw.rect(screen, (40, 130, 50), (0, HORIZON_ROW + shake_y, SCREEN_WIDTH, SCREEN_HEIGHT - HORIZON_ROW))

        # 4. Project all road segments within drawing range
        start_segment_index = int(car_world_z / SEGMENT_LENGTH)
        num_segments = int(DRAW_DISTANCE / SEGMENT_LENGTH)
        
        projected = []
        for i in range(num_segments + 2):
            seg_idx = start_segment_index + i
            world_z = seg_idx * SEGMENT_LENGTH
            cz = world_z - car_world_z
            
            # Prevent division by zero or coordinate inversion behind the camera
            if cz < NEAR_CLIP:
                cz = NEAR_CLIP
                
            scale = CAMERA_DEPTH / cz
            row = HORIZON_ROW + scale * CAMERA_HEIGHT * (SCREEN_HEIGHT / 2) + shake_y
            center_x = road_center(world_z)
            
            left_x = project_x(center_x - LANE_HALF_WIDTH, camera_x, scale) + shake_x
            right_x = project_x(center_x + LANE_HALF_WIDTH, camera_x, scale) + shake_x
            
            rumble_w = LANE_HALF_WIDTH * 0.08
            left_rumble_in = project_x(center_x - LANE_HALF_WIDTH + rumble_w, camera_x, scale) + shake_x
            right_rumble_in = project_x(center_x + LANE_HALF_WIDTH - rumble_w, camera_x, scale) + shake_x
            
            dash_w = LANE_HALF_WIDTH * 0.015
            dash_left = project_x(center_x - dash_w, camera_x, scale) + shake_x
            dash_right = project_x(center_x + dash_w, camera_x, scale) + shake_x
            
            dash_on = (seg_idx % 4) < 2
            stripe_on = (seg_idx % 6) < 3
            
            projected.append({
                'row': row,
                'left_x': left_x,
                'right_x': right_x,
                'left_rumble_in': left_rumble_in,
                'right_rumble_in': right_rumble_in,
                'dash_left': dash_left,
                'dash_right': dash_right,
                'dash_on': dash_on,
                'stripe_on': stripe_on,
                'scale': scale
            })

        # 5. Draw Segments back-to-front
        for i in range(num_segments, -1, -1):
            seg_far = projected[i + 1]
            seg_near = projected[i]
            
            row_far = max(HORIZON_ROW + shake_y, seg_far['row'])
            row_near = max(HORIZON_ROW + shake_y, seg_near['row'])
            
            if row_far == row_near:
                continue
                
            # Grass and Road Colors alternating
            if seg_near['stripe_on']:
                color_grass = (50, 150, 60)
                color_road = (65, 65, 70)
                color_rumble = (200, 40, 40)
            else:
                color_grass = (40, 130, 50)
                color_road = (58, 58, 62)
                color_rumble = (240, 240, 240)
                
            # Draw Grass left & right
            pygame.draw.polygon(screen, color_grass, [
                (0, row_far), (seg_far['left_x'], row_far),
                (seg_near['left_x'], row_near), (0, row_near)
            ])
            pygame.draw.polygon(screen, color_grass, [
                (seg_far['right_x'], row_far), (SCREEN_WIDTH, row_far),
                (SCREEN_WIDTH, row_near), (seg_near['right_x'], row_near)
            ])
            
            # Draw Road
            pygame.draw.polygon(screen, color_road, [
                (seg_far['left_x'], row_far), (seg_far['right_x'], row_far),
                (seg_near['right_x'], row_near), (seg_near['left_x'], row_near)
            ])
            
            # Draw Rumble strips
            pygame.draw.polygon(screen, color_rumble, [
                (seg_far['left_x'], row_far), (seg_far['left_rumble_in'], row_far),
                (seg_near['left_rumble_in'], row_near), (seg_near['left_x'], row_near)
            ])
            pygame.draw.polygon(screen, color_rumble, [
                (seg_far['right_rumble_in'], row_far), (seg_far['right_x'], row_far),
                (seg_near['right_x'], row_near), (seg_near['right_rumble_in'], row_near)
            ])
            
            # Draw Center Dash
            if seg_near['dash_on']:
                pygame.draw.polygon(screen, (240, 240, 240), [
                    (seg_far['dash_left'], row_far), (seg_far['dash_right'], row_far),
                    (seg_near['dash_right'], row_near), (seg_near['dash_left'], row_near)
                ])

        # 6. Collect & Draw Depth-Sorted Sprites (Obstacles + Roadside Trees)
        sprites = []
        
        # Add visible obstacles
        for obstacle in state['obstacles']:
            cz = obstacle.world_z - car_world_z
            if NEAR_CLIP < cz < DRAW_DISTANCE:
                sprites.append((obstacle.world_z, 'obstacle', obstacle))
                
        # Add visible decorations (Pine Trees)
        # Spaced out every 4 segments (600 world units)
        tree_spacing = 4
        first_tree_idx = ((start_segment_index) // tree_spacing + 1) * tree_spacing
        last_tree_idx = ((start_segment_index + num_segments) // tree_spacing) * tree_spacing
        
        for seg_idx in range(first_tree_idx, last_tree_idx + 1, tree_spacing):
            world_z = seg_idx * SEGMENT_LENGTH
            cz = world_z - car_world_z
            if NEAR_CLIP < cz < DRAW_DISTANCE:
                # Alternate sides left (-1) and right (1)
                side = -1 if (seg_idx % (tree_spacing * 2) == 0) else 1
                sprites.append((world_z, 'tree', side))
                
        # Sort depth: farthest first
        sprites.sort(key=lambda s: -s[0])
        
        # Draw sorted sprites
        for world_z, sprite_type, data in sprites:
            cz = world_z - car_world_z
            scale = CAMERA_DEPTH / cz
            
            center_x = road_center(world_z)
            ground_y = HORIZON_ROW + scale * CAMERA_HEIGHT * (SCREEN_HEIGHT / 2) + shake_y
            
            if sprite_type == 'obstacle':
                obstacle = data
                ox = project_x(obstacle.world_x, camera_x, scale) + shake_x
                w = scale * OBSTACLE_WORLD_WIDTH * (SCREEN_WIDTH / 2)
                h = scale * OBSTACLE_WORLD_HEIGHT * (SCREEN_HEIGHT / 2)
                draw_obstacle(screen, ox, ground_y, w, h, scale)
                
            elif sprite_type == 'tree':
                side = data
                # Place trees on grass just outside rumble strips
                tree_x_world = center_x + side * (LANE_HALF_WIDTH + 1400)
                ox = project_x(tree_x_world, camera_x, scale) + shake_x
                w = scale * 1600 * (SCREEN_WIDTH / 2)
                h = scale * 2800 * (SCREEN_HEIGHT / 2)
                draw_tree(screen, ox, ground_y, w, h, scale)

        # 7. Dashboard / Console HUD
        # Console background polygon
        pygame.draw.polygon(screen, (30, 30, 35), [
            (0, SCREEN_HEIGHT), (SCREEN_WIDTH, SCREEN_HEIGHT),
            (SCREEN_WIDTH * 0.75, SCREEN_HEIGHT - 70), (SCREEN_WIDTH * 0.25, SCREEN_HEIGHT - 70),
        ])
        pygame.draw.line(screen, (50, 50, 55), (SCREEN_WIDTH * 0.25, SCREEN_HEIGHT - 70), (SCREEN_WIDTH * 0.75, SCREEN_HEIGHT - 70), 3)

        # Steering wheel indicator (rotates)
        wheel_center = (SCREEN_WIDTH / 2, SCREEN_HEIGHT - 55)
        wheel_radius = 40
        wheel_angle = max(-1.0, min(1.0, handle_pos / 6.0)) * math.radians(90)
        pygame.draw.circle(screen, (45, 45, 50), wheel_center, wheel_radius, width=8)
        pygame.draw.circle(screen, (20, 20, 22), wheel_center, 10)
        
        spoke_angles = [wheel_angle, wheel_angle + math.radians(120), wheel_angle - math.radians(120)]
        for angle in spoke_angles:
            spoke_end = (wheel_center[0] + wheel_radius * math.sin(angle),
                         wheel_center[1] - wheel_radius * math.cos(angle))
            pygame.draw.line(screen, (20, 20, 22), wheel_center, spoke_end, 4)

        # Speedometer Needle gauge on the dashboard
        gauge_center = (int(SCREEN_WIDTH * 0.7) - 10, SCREEN_HEIGHT - 35)
        gauge_radius = 30
        pygame.draw.arc(screen, (60, 60, 65), 
                        (gauge_center[0] - gauge_radius, gauge_center[1] - gauge_radius, gauge_radius * 2, gauge_radius * 2),
                        math.radians(0), math.radians(180), width=4)
        speed_kmh = int(state['speed'] / 10)
        speed_ratio = max(0.0, min(1.0, (state['speed'] - START_SPEED) / (MAX_SPEED - START_SPEED)))
        needle_angle = math.radians(180 - speed_ratio * 180)
        needle_end = (gauge_center[0] + (gauge_radius - 4) * math.cos(needle_angle),
                      gauge_center[1] - (gauge_radius - 4) * math.sin(needle_angle))
        pygame.draw.line(screen, (255, 60, 60), gauge_center, needle_end, 3)
        pygame.draw.circle(screen, (120, 120, 125), gauge_center, 5)

        # Digital speed readout below speedometer
        speed_digit_text = font.render(f"{speed_kmh} KM/H", True, (255, 255, 255))
        screen.blit(speed_digit_text, speed_digit_text.get_rect(center=(gauge_center[0], gauge_center[1] + 15)))
        
        # Redline/Warning indicator
        if speed_kmh > 480: # Redlining near max speed
            if int(time.time() * 6) % 2 == 0:
                warn_text = font.render("REDLINE", True, (255, 50, 50))
                screen.blit(warn_text, warn_text.get_rect(center=(gauge_center[0], gauge_center[1] - 42)))

        # 8. Crash Flash overlay
        if state['crash_freeze'] > 0:
            flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            alpha = int(160 * (state['crash_freeze'] / CRASH_FREEZE_TIME))
            flash.fill((220, 30, 30, alpha))
            screen.blit(flash, (0, 0))

        # 9. Draw HUD text panel
        draw_hud(screen, font, state)

        # Steering fallback notice
        if not haptics.connected:
            hint = font.render("NO HAPKIT DETECTED -- USE LEFT/RIGHT ARROWS", True, (255, 225, 80))
            screen.blit(hint, (SCREEN_WIDTH / 2 - hint.get_width() / 2, HORIZON_ROW - 30))

        # Game over / restart prompt
        if state['game_over']:
            over_text = big_font.render("CRASHED OUT", True, (255, 255, 255))
            score_text = font.render(f"Final distance: {int(state['car_world_z'] / 10):,} m -- Press R to retry or ESC to exit", True, (255, 255, 255))
            
            # Semi-transparent background overlay for game over text
            over_bg = pygame.Surface((SCREEN_WIDTH, 140), pygame.SRCALPHA)
            over_bg.fill((0, 0, 0, 180))
            screen.blit(over_bg, (0, SCREEN_HEIGHT / 2 - 70))
            
            screen.blit(over_text, over_text.get_rect(center=(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 20)))
            screen.blit(score_text, score_text.get_rect(center=(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 35)))

        pygame.display.flip()

    haptics.close()
    pygame.quit()
    sys.exit()


if __name__ == '__main__':
    main()