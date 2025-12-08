# game_engine.py
import displayio
import random
import terminalio
from adafruit_display_text import label


def clear_group(group: displayio.Group) -> None:
    while len(group):
        group.pop()


class Game:
    """
    Dodging game (no display_shapes, only displayio):

    - Player: stick figure bitmap (7x11)
    - Obstacles: 1-pixel-high horizontal bitmaps moving down
    - Left/right movement: via handle_encoder_delta() (called from buttons)
    - Vertical movement: via tilt (accelerometer Y)
    - Every 4 dodged obstacles -> +1 bullet (max 3)
    - Button: spend 1 bullet to destroy one obstacle
    - Bullets shown as small vertical bars at top-right
    - scroll_speed may be float; positions stored as float but drawn as int
    - Player name + score shown at the top of the screen
    """

    def __init__(
        self,
        root_group: displayio.Group,
        level_config: dict,
        player_name: str = "",
        width: int = 128,
        height: int = 64,
    ):
        self.root_group = root_group
        self.width = width
        self.height = height

        clear_group(self.root_group)
        self.group = displayio.Group()
        self.root_group.append(self.group)

        # ----- Level parameters from JSON -----
        self.scroll_speed = float(level_config.get("scroll_speed", 1.0))
        self.spawn_interval = int(level_config.get("spawn_interval_frames", 20))
        self.max_obstacles = int(level_config.get("max_obstacles", 5))
        self.obstacle_min_length = int(level_config.get("obstacle_min_length", 20))
        self.obstacle_max_length = int(level_config.get("obstacle_max_length", 50))

        # Shared palette: index 0 = black, 1 = white
        self.palette = displayio.Palette(2)
        self.palette[0] = 0x000000
        self.palette[1] = 0xFFFFFF

        # ----- Score + Name -----
        self.player_name = player_name if player_name else "PLAYER"
        self.score = 0

        # Name + score label at top
        self.name_score_label = label.Label(
            terminalio.FONT,
            text=self._make_name_score_text(),
            x=2,
            y=8,
        )
        self.group.append(self.name_score_label)

        # ----- Player (stick figure) -----
        # Stick figure bitmap size
        self.player_width = 7
        self.player_height = 11

        self.horizontal_step = 3
        self.vertical_step = self.height // 4  # 1/4 screen per tilt
        self.vertical_level = 0                # 0..2
        self.bottom_y = self.height - self.player_height - 2

        self.player_x = float(self.width // 2)
        self.player_y = float(self.bottom_y)

        player_bitmap = displayio.Bitmap(self.player_width, self.player_height, 2)

        # Draw a simple stick figure:
        #  - head: 3x3 block centered at top
        #  - body: vertical line
        #  - arms: horizontal line
        #  - legs: diagonal-ish lines
        #
        # Coordinate system: (x, y) where x in [0..6], y in [0..10]

        # Head (3x3) roughly centered at top, rows y=0..2
        head_coords = [
            (2, 0), (3, 0), (4, 0),
            (2, 1),         (4, 1),
            (2, 2), (3, 2), (4, 2),
        ]
        for x, y in head_coords:
            player_bitmap[x, y] = 1

        # Body: vertical line down from head center (x=3, y=3..7)
        for y in range(3, 8):
            player_bitmap[3, y] = 1

        # Arms: horizontal line at y=4 (from x=1..5)
        for x in range(1, 6):
            player_bitmap[x, 4] = 1

        # Legs: two lines from (3,8) to (1,10) and (5,10)
        player_bitmap[3, 8] = 1
        player_bitmap[2, 9] = 1
        player_bitmap[1, 10] = 1

        player_bitmap[4, 9] = 1
        player_bitmap[5, 10] = 1

        self.player_tile = displayio.TileGrid(
            player_bitmap,
            pixel_shader=self.palette,
            x=int(self.player_x),
            y=int(self.player_y),
        )
        self.group.append(self.player_tile)

        # ----- Bullets UI -----
        self.bullets = 0
        self.max_bullets = 3
        self.bullet_slots = []

        bullet_w = 2
        bullet_h = 6
        bullet_bitmap = displayio.Bitmap(bullet_w, bullet_h, 2)
        for yy in range(bullet_h):
            for xx in range(bullet_w):
                bullet_bitmap[xx, yy] = 1

        # place bullets a bit lower so they don't overlap name/score
        for i in range(self.max_bullets):
            tile = displayio.TileGrid(
                bullet_bitmap,
                pixel_shader=self.palette,
                x=self.width + 10,  # start off-screen
                y=14 + i * (bullet_h + 1),
            )
            self.group.append(tile)
            self.bullet_slots.append(tile)
        self._update_bullet_display()

        # ----- Obstacles -----
        # each obstacle: {"tile": TileGrid, "y": float, "x": float, "width": int, "dodged": bool}
        self.obstacles = []
        self.frame_count = 0
        self.dodged_count = 0

        # ----- Tilt config -----
        self.tilt_threshold = float(level_config.get("tilt_threshold", 3.0))
        self.tilt_cooldown = 0.3  # seconds
        self.last_tilt_time = 0.0

        # ----- Game over flag -----
        self.game_over = False

    # ------- helper methods -------

    def _make_name_score_text(self) -> str:
        return "{}  S:{}".format(self.player_name, self.score)

    def _update_name_score_label(self):
        if self.name_score_label is not None:
            self.name_score_label.text = self._make_name_score_text()

    def _update_player_pos(self):
        # Clamp vertical level 0..2
        if self.vertical_level < 0:
            self.vertical_level = 0
        if self.vertical_level > 2:
            self.vertical_level = 2

        self.player_y = float(self.bottom_y - self.vertical_level * self.vertical_step)

        # Clamp x for player
        if self.player_x < 0:
            self.player_x = 0.0
        if self.player_x > self.width - self.player_width:
            self.player_x = float(self.width - self.player_width)

        # Apply to TileGrid using ints
        self.player_tile.x = int(self.player_x)
        self.player_tile.y = int(self.player_y)

    def _update_bullet_display(self):
        # Show bullets by moving their TileGrids on/off screen
        for i, tile in enumerate(self.bullet_slots):
            if i < self.bullets:
                tile.x = self.width - 4  # visible
            else:
                tile.x = self.width + 10  # off-screen

    def _spawn_obstacle(self):
        if len(self.obstacles) >= self.max_obstacles:
            return

        length = random.randint(self.obstacle_min_length, self.obstacle_max_length)
        x = float(random.randint(0, self.width - length))
        y = 0.0

        bitmap = displayio.Bitmap(length, 1, 2)
        for xx in range(length):
            bitmap[xx, 0] = 1

        tile = displayio.TileGrid(
            bitmap,
            pixel_shader=self.palette,
            x=int(x),
            y=int(y),
        )
        self.group.append(tile)

        self.obstacles.append(
            {"tile": tile, "y": y, "x": x, "width": length, "dodged": False}
        )

    def _check_collision(self, obs):
        # Player AABB (now using width/height of stick figure)
        px0 = int(self.player_x)
        px1 = px0 + self.player_width
        py0 = int(self.player_y)
        py1 = py0 + self.player_height

        # Obstacle rectangle (1 pixel tall)
        oy = int(obs["y"])
        ox0 = int(obs["x"])
        ox1 = ox0 + obs["width"]
        oy0 = oy
        oy1 = oy + 1

        return (px0 < ox1 and px1 > ox0 and py0 < oy1 and py1 > oy0)

    def _handle_obstacles(self):
        if self.game_over:
            return

        to_remove = []

        for obs in self.obstacles:
            # Move with float, draw as int
            obs["y"] += self.scroll_speed
            y = obs["y"]

            tile = obs["tile"]
            tile.y = int(y)
            tile.x = int(obs["x"])

            # Check collision
            if self._check_collision(obs):
                self.game_over = True
                return

            # Off-screen?
            if int(y) > self.height:
                to_remove.append(obs)
                if not obs["dodged"]:
                    obs["dodged"] = True
                    # +1 score for dodged obstacle
                    self.score += 1
                    self._update_name_score_label()

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
        """
        Used by your code to move the player left/right.
        In your setup, you call this from the left/right buttons,
        not from the rotary encoder rotation.
        """
        if self.game_over:
            return
        if delta == 0:
            return

        self.player_x += float(delta * self.horizontal_step)
        self._update_player_pos()

    def handle_button_press(self):
        """
        Called when the shoot button is pressed.
        Spends 1 bullet to destroy the first obstacle, if any.
        +1 score for each destroyed obstacle.
        """
        if self.game_over:
            return
        if self.bullets <= 0:
            return
        if not self.obstacles:
            return

        obs = self.obstacles.pop(0)
        self.group.remove(obs["tile"])
        self.bullets -= 1
        self._update_bullet_display()

        # +1 score for destroyed obstacle
        self.score += 1
        self._update_name_score_label()

    def update(self, accel_y: float, now: float):
        """
        Called every frame from the main loop.
        Handles tilt-based vertical movement, spawning, and obstacle motion.
        """
        if self.game_over:
            return

        self.frame_count += 1

        # Tilt-based vertical movement with cooldown
        if now - self.last_tilt_time > self.tilt_cooldown:
            if accel_y < -self.tilt_threshold:
                if self.vertical_level < 2:
                    self.vertical_level += 1
                    self.last_tilt_time = now
            elif accel_y > self.tilt_threshold:
                if self.vertical_level > 0:
                    self.vertical_level -= 1
                    self.last_tilt_time = now

            self._update_player_pos()

        # Spawn obstacles periodically
        if self.spawn_interval > 0 and (self.frame_count % self.spawn_interval == 0):
            self._spawn_obstacle()

        # Move / remove / collide
        self._handle_obstacles()
