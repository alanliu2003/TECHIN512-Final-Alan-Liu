# game_engine.py
import displayio
import random


def clear_group(group: displayio.Group) -> None:
    while len(group):
        group.pop()


class Game:
    """
    Dodging game without adafruit_display_shapes:
    - Player: square bitmap
    - Obstacles: 1-pixel-high horizontal bitmaps moving down
    - Rotary encoder: move left/right
    - Accelerometer tilt: move up/down in 1/4-screen steps
    - Every 4 dodged obstacles -> +1 bullet (max 3)
    - Button: spend 1 bullet to destroy one obstacle
    - Bullets shown as small vertical bars at top-right
    """

    def __init__(self, root_group: displayio.Group, level_config: dict,
                 width: int = 128, height: int = 64):
        self.root_group = root_group
        self.width = width
        self.height = height

        clear_group(self.root_group)
        self.group = displayio.Group()
        self.root_group.append(self.group)

        # ----- Level parameters from JSON -----
        self.scroll_speed = level_config.get("scroll_speed", 1)
        self.spawn_interval = level_config.get("spawn_interval_frames", 20)
        self.max_obstacles = level_config.get("max_obstacles", 5)
        self.obstacle_min_length = level_config.get("obstacle_min_length", 20)
        self.obstacle_max_length = level_config.get("obstacle_max_length", 50)

        # Shared palette: index 0 = black, 1 = white
        self.palette = displayio.Palette(2)
        self.palette[0] = 0x000000
        self.palette[1] = 0xFFFFFF

        # ----- Player -----
        self.player_size = 8
        self.player_radius = self.player_size // 2  # used for simple collision
        self.horizontal_step = 3  # pixels per encoder step
        self.vertical_step = self.height // 4       # 1/4 screen per tilt
        self.vertical_level = 0                     # 0 bottom, up to 2 (half screen)
        self.bottom_y = self.height - self.player_size - 2
        self.player_x = self.width // 2
        self.player_y = self.bottom_y

        player_bitmap = displayio.Bitmap(self.player_size, self.player_size, 2)
        for y in range(self.player_size):
            for x in range(self.player_size):
                player_bitmap[x, y] = 1  # white square

        self.player_tile = displayio.TileGrid(
            player_bitmap,
            pixel_shader=self.palette,
            x=self.player_x,
            y=self.player_y,
        )
        self.group.append(self.player_tile)

        # ----- Bullets UI (vertical bars in top-right) -----
        self.bullets = 0
        self.max_bullets = 3
        self.bullet_slots = []

        bullet_w = 2
        bullet_h = 6
        bullet_bitmap = displayio.Bitmap(bullet_w, bullet_h, 2)
        for y in range(bullet_h):
            for x in range(bullet_w):
                bullet_bitmap[x, y] = 1

        for i in range(self.max_bullets):
            # stack them downward from top-right corner
            tile = displayio.TileGrid(
                bullet_bitmap,
                pixel_shader=self.palette,
                x=self.width - (bullet_w + 2),
                y=2 + i * (bullet_h + 1),
            )
            # initially "empty" -> make them black; we'll re-color when needed
            tile.pixel_shader = self.palette
            self.group.append(tile)
            self.bullet_slots.append(tile)
        self._update_bullet_display()

        # ----- Obstacles -----
        # each obstacle: {"tile": TileGrid, "y": int, "x": int, "width": int, "dodged": bool}
        self.obstacles = []
        self.frame_count = 0
        self.dodged_count = 0

        # ----- Tilt config -----
        self.tilt_threshold = level_config.get("tilt_threshold", 3.0)
        self.tilt_cooldown = 0.3  # seconds
        self.last_tilt_time = 0.0

    # ------- helper methods -------

    def _update_player_pos(self):
        # clamp vertical level
        if self.vertical_level < 0:
            self.vertical_level = 0
        if self.vertical_level > 2:  # half screen
            self.vertical_level = 2

        self.player_y = self.bottom_y - self.vertical_level * self.vertical_step

        # clamp x
        if self.player_x < 0:
            self.player_x = 0
        if self.player_x > self.width - self.player_size:
            self.player_x = self.width - self.player_size

        self.player_tile.x = self.player_x
        self.player_tile.y = self.player_y

    def _update_bullet_display(self):
        # slots are all white bitmaps; we "hide" them by shifting them off-screen
        # or just by overlaying with background color
        for i, tile in enumerate(self.bullet_slots):
            # simplest: move "empty" ones slightly off screen
            if i < self.bullets:
                tile.x = self.width - 4  # visible
            else:
                tile.x = self.width + 10  # off-screen to the right

    def _spawn_obstacle(self):
        if len(self.obstacles) >= self.max_obstacles:
            return

        length = random.randint(self.obstacle_min_length, self.obstacle_max_length)
        x = random.randint(0, self.width - length)
        y = 0

        # 1-pixel-high horizontal line bitmap
        bitmap = displayio.Bitmap(length, 1, 2)
        for xx in range(length):
            bitmap[xx, 0] = 1

        tile = displayio.TileGrid(
            bitmap,
            pixel_shader=self.palette,
            x=x,
            y=y,
        )
        self.group.append(tile)

        self.obstacles.append(
            {"tile": tile, "y": y, "x": x, "width": length, "dodged": False}
        )

    def _check_collision(self, obs):
        # player AABB
        px0 = self.player_x
        px1 = self.player_x + self.player_size
        py0 = self.player_y
        py1 = self.player_y + self.player_size

        # obstacle rectangle (1-pixel-high line)
        ox0 = obs["x"]
        ox1 = obs["x"] + obs["width"]
        oy0 = obs["y"]
        oy1 = obs["y"] + 1

        # basic rectangle intersection
        if (px0 < ox1 and px1 > ox0 and py0 < oy1 and py1 > oy0):
            return True
        return False

    def _handle_obstacles(self):
        to_remove = []

        for obs in self.obstacles:
            obs["y"] += self.scroll_speed
            y = obs["y"]
            obs["tile"].y = y

            if self._check_collision(obs):
                # simple "reset": remove all obstacles & ammo
                for o in self.obstacles:
                    self.group.remove(o["tile"])
                self.obstacles = []
                self.dodged_count = 0
                self.bullets = 0
                self._update_bullet_display()
                return

            if y > self.height:
                to_remove.append(obs)
                if not obs["dodged"]:
                    obs["dodged"] = True
                    self.dodged_count += 1
                    if (self.dodged_count % 4 == 0) and (
                        self.bullets < self.max_bullets
                    ):
                        self.bullets += 1
                        self._update_bullet_display()

        for obs in to_remove:
            if obs in self.obstacles:
                self.obstacles.remove(obs)
                self.group.remove(obs["tile"])

    # ------- public API -------

    def handle_encoder_delta(self, delta: int):
        """Move player left/right based on encoder delta."""
        if delta == 0:
            return
        self.player_x += delta * self.horizontal_step
        self._update_player_pos()

    def handle_button_press(self):
        """Use a bullet to instantly destroy one obstacle (no projectile animation)."""
        if self.bullets <= 0:
            return
        if not self.obstacles:
            return

        obs = self.obstacles.pop(0)
        self.group.remove(obs["tile"])
        self.bullets -= 1
        self._update_bullet_display()

    def update(self, accel_y: float, now: float):
        """Called every frame from the main loop."""
        self.frame_count += 1

        # Tilt-based vertical movement
        if now - self.last_tilt_time > self.tilt_cooldown:
            if accel_y < -self.tilt_threshold:
                # tilt down -> move player up
                if self.vertical_level < 2:
                    self.vertical_level += 1
                    self.last_tilt_time = now
            elif accel_y > self.tilt_threshold:
                # tilt up -> move player down
                if self.vertical_level > 0:
                    self.vertical_level -= 1
                    self.last_tilt_time = now

            self._update_player_pos()

        # Spawn obstacles periodically
        if self.frame_count % self.spawn_interval == 0:
            self._spawn_obstacle()

        # Move / remove / collide
        self._handle_obstacles()