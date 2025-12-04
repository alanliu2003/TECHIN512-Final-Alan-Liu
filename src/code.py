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
BUTTON_PIN    = board.D8

# ------------------------
# DISPLAY + I2C
# ------------------------
displayio.release_displays()

i2c = busio.I2C(board.SCL, board.SDA)
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

main_group = displayio.Group()
display.root_group = main_group

# Accelerometer
accelerometer = adafruit_adxl34x.ADXL345(i2c)

# ------------------------
# ENCODER + BUTTON (unchanged sensitivity)
# ------------------------
encoder = RotaryEncoder(
    ENCODER_PIN_A,
    ENCODER_PIN_B,
    debounce_ms=3,
    pulses_per_detent=3
)
last_encoder_position = encoder.position

button = DigitalInOut(BUTTON_PIN)
button.direction = Direction.INPUT
button.pull = Pull.UP
last_button_state = button.value  # True = released, False = pressed

# ------------------------
# STATE
# ------------------------
mode = "main_menu"        # "main_menu", "difficulty", "game", "game_over"
menu_index = 0
difficulty_index = 0
game_over_index = 0

selected_difficulty = None
current_level_config = None
game = None  # Game instance


def turn_off_display_and_exit():
    display.root_group = displayio.Group()
    displayio.release_displays()
    while True:
        pass  # halt


def load_level_config_for_difficulty(difficulty_name: str) -> dict:
    filename = "/levels/{}.json".format(difficulty_name.lower())
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except OSError:
        # fallback defaults
        return {
            "name": difficulty_name,
            "scroll_speed": 1 if difficulty_name == "Easy" else
                            2 if difficulty_name == "Medium" else 3,
            "spawn_interval_frames": 25 if difficulty_name == "Easy" else
                                     18 if difficulty_name == "Medium" else 12,
            "max_obstacles": 4 if difficulty_name == "Easy" else
                             6 if difficulty_name == "Medium" else 8,
            "obstacle_min_length": 20,
            "obstacle_max_length": 50,
            "tilt_threshold": 3.0
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
    # --- ENCODER ---
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
                difficulty_index = (difficulty_index + 1) % len(
                    menu_screens.DIFFICULTY_OPTIONS
                )
            elif delta < 0:
                difficulty_index = (difficulty_index - 1) % len(
                    menu_screens.DIFFICULTY_OPTIONS
                )
            menu_screens.show_difficulty_menu(main_group, difficulty_index)

        elif mode == "game" and game is not None:
            game.handle_encoder_delta(delta)

        elif mode == "game_over":
            if delta > 0:
                game_over_index = (game_over_index + 1) % len(
                    menu_screens.GAME_OVER_OPTIONS
                )
            elif delta < 0:
                game_over_index = (game_over_index - 1) % len(
                    menu_screens.GAME_OVER_OPTIONS
                )
            menu_screens.show_game_over_menu(main_group, game_over_index)

        last_encoder_position = pos

    # --- BUTTON (edge detect) ---
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
            current_level_config = load_level_config_for_difficulty(selected_difficulty)
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

    # --- GAME UPDATE ---
    if mode == "game" and game is not None:
        ax, ay, az = accelerometer.acceleration
        now = time.monotonic()
        game.update(ay, now)
        if game.game_over:
            mode = "game_over"
            game_over_index = 0
            menu_screens.show_game_over_menu(main_group, game_over_index)

    time.sleep(0.01)
