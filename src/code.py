# code.py
import time
import json
import board
import busio
import displayio
import i2cdisplaybus
import adafruit_displayio_ssd1306
from rotary_encoder import RotaryEncoder
from digitalio import DigitalInOut, Direction, Pull
import adafruit_adxl34x

import menu_screens
import game_engine

# ------------------------
# PIN CONFIG
# ------------------------
ENCODER_PIN_A = board.D9
ENCODER_PIN_B = board.D10

BUTTON_PIN       = board.D8   # main button: confirm / shoot
LEFT_BUTTON_PIN  = board.D0   # move left in game
RIGHT_BUTTON_PIN = board.D1   # move right in game

# ------------------------
# DISPLAY + I2C
# ------------------------
displayio.release_displays()

i2c = busio.I2C(board.SCL, board.SDA)
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

main_group = displayio.Group()
display.root_group = main_group

# Accelerometer (ADXL345)
accelerometer = adafruit_adxl34x.ADXL345(i2c)

# ------------------------
# ENCODER + BUTTONS
# ------------------------
encoder = RotaryEncoder(
    ENCODER_PIN_A,
    ENCODER_PIN_B,
    debounce_ms=3,
    pulses_per_detent=3    # encoder only used for menus
)
last_encoder_position = encoder.position

button = DigitalInOut(BUTTON_PIN)
button.direction = Direction.INPUT
button.pull = Pull.UP
last_button_state = button.value  # True = released, False = pressed

left_button = DigitalInOut(LEFT_BUTTON_PIN)
left_button.direction = Direction.INPUT
left_button.pull = Pull.UP

right_button = DigitalInOut(RIGHT_BUTTON_PIN)
right_button.direction = Direction.INPUT
right_button.pull = Pull.UP

# ------------------------
# STATE
# ------------------------
mode = "main_menu"        # "main_menu", "difficulty", "level_select", "game", "game_over"
menu_index = 0
difficulty_index = 0
level_index = 0           # 0..9 (10 levels)
game_over_index = 0

selected_difficulty = None
selected_level = None     # 1..10
current_level_config = None
game = None  # Game instance


def turn_off_display_and_exit():
    display.root_group = displayio.Group()
    displayio.release_displays()
    while True:
        pass  # halt


def load_level_config(difficulty_name: str, level_number: int) -> dict:
    """
    Load config for a specific difficulty + level.
    1) Try /levels/<difficulty>_<level>.json  (easy_01.json, hard_10.json, etc.)
    2) If missing, synthesize sensible defaults using:
       - difficulty: obstacle min/max length
       - level: scroll speed, spawn interval, max obstacles, tilt threshold
    """
    # ------------------------
    # 1) Try JSON override
    # ------------------------
    diff_key = difficulty_name.lower()
    filename = "/levels/{}_{}.json".format(
        diff_key,
        str(level_number).zfill(2)  # 01, 02, ..., 10
    )
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except OSError:
        pass  # no file, fall back to generated config

    # ------------------------
    # 2) Generated config
    # ------------------------
    # Base per-difficulty obstacle sizes
    if difficulty_name == "Easy":
        base_scroll = 1
        base_spawn = 28
        base_max_obs = 4
        obst_min = 28
        obst_max = 48
    elif difficulty_name == "Medium":
        base_scroll = 2
        base_spawn = 20
        base_max_obs = 6
        obst_min = 22
        obst_max = 40
    else:  # "Hard"
        base_scroll = 3
        base_spawn = 14
        base_max_obs = 8
        obst_min = 16
        obst_max = 34

    # Level number modifies difficulty:
    # - scroll_speed increases slightly
    # - spawn_interval_frames decreases
    # - max_obstacles increases every few levels
    # - tilt_threshold gets a bit tighter
    ln = max(1, min(level_number, 10))
    # slow bump in scroll speed
    scroll_speed = base_scroll + (ln - 1) // 4  # +1 every 4 levels
    # spawn interval decreases almost linearly with level
    spawn_interval_frames = max(6, base_spawn - (ln - 1) * 2)
    # max obstacles increases modestly
    max_obstacles = base_max_obs + (ln - 1) // 3
    # tilt threshold slightly tighter on higher levels
    tilt_threshold = max(1.5, 3.0 - (ln - 1) * 0.15)

    return {
        "name": "{} L{}".format(difficulty_name, ln),
        "scroll_speed": scroll_speed,
        "spawn_interval_frames": spawn_interval_frames,
        "max_obstacles": max_obstacles,
        "obstacle_min_length": obst_min,
        "obstacle_max_length": obst_max,
        "tilt_threshold": tilt_threshold,
    }


# ------------------------
# SPLASH + INITIAL MAIN MENU
# ------------------------
menu_screens.show_splash_screen(main_group)
time.sleep(2.0)  # show splash briefly
menu_screens.show_main_menu(main_group, menu_index)

# ------------------------
# MAIN LOOP
# ------------------------
while True:
    # --- ENCODER: MENUS ONLY ---
    changed = encoder.update()
    if changed:
        pos = encoder.position
        delta = pos - last_encoder_position

        if mode == "main_menu":
            if delta > 0:
                menu_index = (menu_index + 1) % len(menu_screens.MAIN_MENU_OPTIONS)
            elif delta < 0:
                menu_index = (menu_index - 1) % len(menu_screens.MAIN_MENU_OPTIONS)
            menu_screens.show_main_menu(main_group, menu_index)

        elif mode == "difficulty":
            if delta > 0:
                difficulty_index = (difficulty_index + 1) % len(menu_screens.DIFFICULTY_OPTIONS)
            elif delta < 0:
                difficulty_index = (difficulty_index - 1) % len(menu_screens.DIFFICULTY_OPTIONS)
            menu_screens.show_difficulty_menu(main_group, difficulty_index)

        elif mode == "level_select":
            if delta > 0:
                level_index = (level_index + 1) % menu_screens.LEVEL_COUNT
            elif delta < 0:
                level_index = (level_index - 1) % menu_screens.LEVEL_COUNT
            # show level screen using selected difficulty name
            diff_name = menu_screens.DIFFICULTY_OPTIONS[difficulty_index]
            menu_screens.show_level_menu(main_group, diff_name, level_index)

        elif mode == "game_over":
            if delta > 0:
                game_over_index = (game_over_index + 1) % len(menu_screens.GAME_OVER_OPTIONS)
            elif delta < 0:
                game_over_index = (game_over_index - 1) % len(menu_screens.GAME_OVER_OPTIONS)
            menu_screens.show_game_over_menu(main_group, game_over_index)

        # NOTE: encoder no longer moves the player at all
        last_encoder_position = pos

    # --- MAIN BUTTON (edge detect) ---
    current_button_state = button.value  # True = released, False = pressed
    if last_button_state and not current_button_state:
        # just pressed
        if mode == "main_menu":
            choice = menu_screens.MAIN_MENU_OPTIONS[menu_index]
            if choice == "Start Game":
                mode = "difficulty"
                last_encoder_position = encoder.position
                menu_screens.show_difficulty_menu(main_group, difficulty_index)
            else:
                turn_off_display_and_exit()

        elif mode == "difficulty":
            # We only choose difficulty here; level comes next
            selected_difficulty = menu_screens.DIFFICULTY_OPTIONS[difficulty_index]
            level_index = 0  # default to Level 1
            mode = "level_select"
            last_encoder_position = encoder.position
            menu_screens.show_level_menu(main_group, selected_difficulty, level_index)

        elif mode == "level_select":
            # Confirm level selection -> start game
            selected_level = level_index + 1  # convert 0-based to 1-based
            current_level_config = load_level_config(selected_difficulty, selected_level)
            game = game_engine.Game(main_group, current_level_config)
            mode = "game"
            last_encoder_position = encoder.position

        elif mode == "game" and game is not None:
            # fire bullet
            game.handle_button_press()

        elif mode == "game_over":
            choice = menu_screens.GAME_OVER_OPTIONS[game_over_index]
            if choice == "Restart":
                if current_level_config is not None:
                    game = game_engine.Game(main_group, current_level_config)
                    mode = "game"
                    last_encoder_position = encoder.position
            else:  # "Main Menu"
                mode = "main_menu"
                menu_index = 0
                menu_screens.show_main_menu(main_group, menu_index)
                last_encoder_position = encoder.position

    last_button_state = current_button_state

    # --- GAME UPDATE (movement + obstacles) ---
    if mode == "game" and game is not None:
        # Left/right movement via buttons (active LOW)
        if not left_button.value:
            game.handle_encoder_delta(-1)   # move left
        if not right_button.value:
            game.handle_encoder_delta(1)    # move right

        # Tilt-based vertical movement + obstacle spawning/motion
        ax, ay, az = accelerometer.acceleration
        now = time.monotonic()
        game.update(ay, now)

        # Check for collision -> game over menu
        if game.game_over:
            mode = "game_over"
            game_over_index = 0
            menu_screens.show_game_over_menu(main_group, game_over_index)

    time.sleep(0.01)
