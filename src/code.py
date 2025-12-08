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
import neopixel

import menu_screens
import game_engine
import terminalio
from adafruit_display_text import label


SCORES_FILE = "/scores.json"

# High score display state
last_player_score = 0
last_high_scores = []  # list of {"name": str, "score": int}


# ------------------------
# PIN CONFIG
# ------------------------
ENCODER_PIN_A = board.D9
ENCODER_PIN_B = board.D10

BUTTON_PIN       = board.D8   # main button: confirm / shoot
LEFT_BUTTON_PIN  = board.D0   # move left in game / name letter -
RIGHT_BUTTON_PIN = board.D1   # move right in game / name letter +
ENCODER_BUTTON_PIN = board.D7 # encoder push button: finish name entry

PIXEL_PIN = board.D2

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

# NeoPixel (status LED)
pixel = neopixel.NeoPixel(PIXEL_PIN, 1, brightness=0.3, auto_write=True)
pixel[0] = (255, 255, 255)  # default white (menus)

# --- LED flash state for game over ---
FLASH_INTERVAL = 0.1   # seconds between flashes
FLASH_COUNT_LIMIT = 6  # total on/off toggles

flash_active = False
flash_last_time = 0.0
flash_count = 0
prev_game_over = False

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
last_left_state = left_button.value

right_button = DigitalInOut(RIGHT_BUTTON_PIN)
right_button.direction = Direction.INPUT
right_button.pull = Pull.UP
last_right_state = right_button.value

encoder_button = DigitalInOut(ENCODER_BUTTON_PIN)
encoder_button.direction = Direction.INPUT
encoder_button.pull = Pull.UP
last_encoder_button_state = encoder_button.value

# ------------------------
# STATE
# ------------------------
# modes: "main_menu", "difficulty", "level_select", "name_entry", "game", "game_over"
mode = "main_menu"
menu_index = 0
difficulty_index = 0
level_index = 0           # 0..9 (10 levels)
game_over_index = 0

selected_difficulty = None
selected_level = None     # 1..10
current_level_config = None
game = None  # Game instance

# Name entry state
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
current_name = ""
current_char_index = 0  # index into ALPHABET
MAX_NAME_LENGTH = 10


def turn_off_display_and_exit():
    display.root_group = displayio.Group()
    displayio.release_displays()
    while True:
        pass  # halt


def load_level_config(difficulty_name: str, level_number: int) -> dict:
    """
    Load config for a specific difficulty + level.
    1) Try /levels/<difficulty>_<level>.json  (easy_01.json, hard_10.json, etc.)
    2) If missing, synthesize sensible defaults.
    """
    diff_key = difficulty_name.lower()
    level_str = f"{level_number:02d}"

    # 1) Try JSON override
    filename = "/levels/{}_{}.json".format(diff_key, level_str)
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except OSError:
        pass  # no file, fall back to generated config

    # 2) Generated config
    # Base per-difficulty obstacle sizes + scroll speed and max_obstacles differences
    if difficulty_name == "Easy":
        base_scroll = 1.0
        base_spawn = 28
        base_max_obs = 3
        obst_min = 28
        obst_max = 48
    elif difficulty_name == "Medium":
        base_scroll = 1.8
        base_spawn = 22
        base_max_obs = 5
        obst_min = 22
        obst_max = 40
    else:  # "Hard"
        base_scroll = 2.5
        base_spawn = 16
        base_max_obs = 7
        obst_min = 16
        obst_max = 34

    ln = max(1, min(level_number, 10))

    # scroll speed slightly increases with level
    scroll_speed = base_scroll + (ln - 1) * 0.15
    # spawn interval decreases
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

def load_all_scores():
    """Load global scores dict from flash."""
    try:
        with open(SCORES_FILE, "r") as f:
            return json.load(f)
    except OSError:
        # file missing
        return {}
    except ValueError:
        # corrupted JSON
        return {}


def save_all_scores(data):
    """Save global scores dict to flash."""
    try:
        with open(SCORES_FILE, "w") as f:
            json.dump(data, f)
    except OSError:
        # If write fails, just ignore (no crash)
        pass


def update_high_scores(difficulty_name: str, level_number: int, player_name: str, score: int):
    """
    Update high scores for a specific (difficulty, level),
    keep only top 5, and return the list for that level.
    """
    data = load_all_scores()
    diff_key = difficulty_name.lower()
    level_str = f"{level_number:02d}"
    key = "{}_{}".format(diff_key, level_str)

    entries = data.get(key, [])
    entries.append({"name": player_name if player_name else "PLAYER", "score": int(score)})

    # Sort descending by score
    entries.sort(key=lambda e: e.get("score", 0), reverse=True)
    # Keep top 5
    entries = entries[:5]
    data[key] = entries

    save_all_scores(data)
    return entries


def run_animated_splash(group, width=128, height=64):
    """Show 'welcome to dodge game' at top and animate stick figure at bottom."""
    # clear group
    while len(group):
        group.pop()

    # simple 2-color palette
    palette = displayio.Palette(2)
    palette[0] = 0x000000  # black
    palette[1] = 0xFFFFFF  # white

    # Title text at top
    title = label.Label(
        terminalio.FONT,
        text="welcome to dodge game",
        x=0,
        y=10,
    )
    group.append(title)

    # --- Stick figure bitmap (same design as in Game) ---
    player_w = 7
    player_h = 11
    player_bitmap = displayio.Bitmap(player_w, player_h, 2)

    # Head (3x3) centered at top
    head_coords = [
        (2, 0), (3, 0), (4, 0),
        (2, 1),         (4, 1),
        (2, 2), (3, 2), (4, 2),
    ]
    for x, y in head_coords:
        player_bitmap[x, y] = 1

    # Body: vertical line
    for y in range(3, 8):
        player_bitmap[3, y] = 1

    # Arms: horizontal line
    for x in range(1, 6):
        player_bitmap[x, 4] = 1

    # Legs
    player_bitmap[3, 8] = 1
    player_bitmap[2, 9] = 1
    player_bitmap[1, 10] = 1

    player_bitmap[4, 9] = 1
    player_bitmap[5, 10] = 1

    # Place figure near bottom
    start_x = 0
    y_pos = height - player_h - 2
    player_tile = displayio.TileGrid(
        player_bitmap,
        pixel_shader=palette,
        x=int(start_x),
        y=int(y_pos),
    )
    group.append(player_tile)

    # Animate left-right for about 2 seconds
    x = float(start_x)
    dx = 2.0
    start_time = time.monotonic()
    while time.monotonic() - start_time < 2.0:
        x += dx
        if x < 0:
            x = 0
            dx = -dx
        if x > width - player_w:
            x = width - player_w
            dx = -dx

        player_tile.x = int(x)
        time.sleep(0.05)
# ------------------------
# SPLASH + INITIAL MAIN MENU
# ------------------------
run_animated_splash(main_group, width=128, height=64)
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
            diff_name = menu_screens.DIFFICULTY_OPTIONS[difficulty_index]
            menu_screens.show_level_menu(main_group, diff_name, level_index)

        elif mode == "game_over":
            if delta > 0:
                game_over_index = (game_over_index + 1) % len(menu_screens.GAME_OVER_OPTIONS)
            elif delta < 0:
                game_over_index = (game_over_index - 1) % len(menu_screens.GAME_OVER_OPTIONS)
            menu_screens.show_game_over_menu(
                main_group,
                game_over_index,
                last_player_score,
                last_high_scores,
            )

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
            selected_difficulty = menu_screens.DIFFICULTY_OPTIONS[difficulty_index]
            level_index = 0  # default to Level 1
            mode = "level_select"
            last_encoder_position = encoder.position
            menu_screens.show_level_menu(main_group, selected_difficulty, level_index)

        elif mode == "level_select":
            # Confirm level selection -> go to name entry
            selected_level = level_index + 1
            current_level_config = load_level_config(selected_difficulty, selected_level)
            current_name = ""
            current_char_index = 0  # 'A'
            mode = "name_entry"
            menu_screens.show_name_entry(
                main_group,
                current_name,
                ALPHABET[current_char_index],
            )
            last_encoder_position = encoder.position

        elif mode == "name_entry":
            # Add current character to name (if not exceeding max length)
            if len(current_name) < MAX_NAME_LENGTH:
                current_name += ALPHABET[current_char_index]
            # Reset current char back to 'A'
            current_char_index = 0
            menu_screens.show_name_entry(
                main_group,
                current_name,
                ALPHABET[current_char_index],
            )

        elif mode == "game" and game is not None:
            # fire bullet
            game.handle_button_press()

        elif mode == "game_over":
            choice = menu_screens.GAME_OVER_OPTIONS[game_over_index]
            if choice == "Restart":
                if current_level_config is not None:
                    game = game_engine.Game(
                        main_group,
                        current_level_config,
                        player_name=current_name,
                    )
                    mode = "game"
                    prev_game_over = False
                    flash_active = False
                    flash_count = 0
                    last_encoder_position = encoder.position
            else:  # "Main Menu"
                mode = "main_menu"
                menu_index = 0
                menu_screens.show_main_menu(main_group, menu_index)
                last_encoder_position = encoder.position

    last_button_state = current_button_state

    # --- ENCODER BUTTON (finish name entry) ---
    current_enc_btn_state = encoder_button.value
    if last_encoder_button_state and not current_enc_btn_state:
        # pressed
        if mode == "name_entry" and current_level_config is not None:
            # If name is empty, allow that, or you could default to "PLAYER"
            # Create game with current_name
            game = game_engine.Game(
                main_group,
                current_level_config,
                player_name=current_name,
            )
            mode = "game"
            prev_game_over = False
            flash_active = False
            flash_count = 0
            last_encoder_position = encoder.position
    last_encoder_button_state = current_enc_btn_state

    # --- NAME ENTRY: LEFT/RIGHT CHANGE CHAR (edge detect) ---
    if mode == "name_entry":
        current_left_state = left_button.value
        current_right_state = right_button.value

        # left button: previous letter
        if last_left_state and not current_left_state:
            current_char_index = (current_char_index - 1) % len(ALPHABET)
            menu_screens.show_name_entry(
                main_group,
                current_name,
                ALPHABET[current_char_index],
            )

        # right button: next letter
        if last_right_state and not current_right_state:
            current_char_index = (current_char_index + 1) % len(ALPHABET)
            menu_screens.show_name_entry(
                main_group,
                current_name,
                ALPHABET[current_char_index],
            )

        last_left_state = current_left_state
        last_right_state = current_right_state
    else:
        # still update last states so edges are correct when re-entering name_entry
        last_left_state = left_button.value
        last_right_state = right_button.value

    # --- GAME UPDATE (movement + obstacles) ---
    if mode == "game" and game is not None:
        # Left/right movement via buttons (active LOW)
        if not left_button.value:
            game.handle_encoder_delta(-1)   # move left
        if not right_button.value:
            game.handle_encoder_delta(1)    # move right

        ax, ay, az = accelerometer.acceleration
        now = time.monotonic()
        game.update(ay, now)

        # Detect transition into game_over
        if game.game_over and not prev_game_over:
            # Update high scores for this (difficulty, level)
            last_player_score = game.score
            # selected_difficulty and selected_level are already tracked
            last_high_scores = update_high_scores(
                selected_difficulty,
                selected_level,
                current_name,
                last_player_score,
            )

            mode = "game_over"
            game_over_index = 0
            menu_screens.show_game_over_menu(
                main_group,
                game_over_index,
                last_player_score,
                last_high_scores,
            )

            # start LED flash sequence
            flash_active = True
            flash_last_time = now
            flash_count = 0

        prev_game_over = game.game_over


    # --- PIXEL LED STATE ---
    now = time.monotonic()

    if flash_active:
        # Flashing red on/off
        if now - flash_last_time >= FLASH_INTERVAL:
            flash_last_time = now
            flash_count += 1

            if flash_count % 2 == 1:
                pixel[0] = (255, 0, 0)   # red
            else:
                pixel[0] = (0, 0, 0)     # off

            if flash_count >= FLASH_COUNT_LIMIT:
                flash_active = False
    else:
        # Normal LED state
        if game is not None and game.game_over:
            pixel[0] = (255, 0, 0)         # solid red
        elif mode == "game" and game is not None:
            if game.bullets > 0:
                pixel[0] = (255, 255, 0)   # yellow
            else:
                pixel[0] = (0, 255, 0)     # green
        else:
            # any menu / splash / name entry / level select
            pixel[0] = (255, 255, 255)     # white

    time.sleep(0.01)
