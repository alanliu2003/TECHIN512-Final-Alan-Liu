# code.py
import time
import board
import busio
import displayio
import i2cdisplaybus
import adafruit_displayio_ssd1306
from rotary_encoder import RotaryEncoder
from digitalio import DigitalInOut, Direction, Pull

import menu_screens  # our other file

# ------------------------
# PIN CONFIG (change if needed)
# ------------------------
ENCODER_PIN_A = board.D9   # encoder A pin
ENCODER_PIN_B = board.D10  # encoder B pin
BUTTON_PIN    = board.D8   # push button pin

# ------------------------
# DISPLAY SETUP
# ------------------------
displayio.release_displays()

i2c = busio.I2C(board.SCL, board.SDA)
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

main_group = displayio.Group()
display.root_group = main_group

# ------------------------
# ENCODER + BUTTON SETUP
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
# STATE VARIABLES
# ------------------------
mode = "main_menu"          # "main_menu", "difficulty", "game"
menu_index = 0
difficulty_index = 0
selected_difficulty = None

# initial screen
menu_screens.show_main_menu(main_group, menu_index)


def turn_off_display_and_exit():
    display.root_group = displayio.Group()
    displayio.release_displays()
    while True:
        pass  # halt


# ------------------------
# MAIN LOOP
# ------------------------
while True:
    # ----- ENCODER -----
    changed = encoder.update()
    if changed:
        pos = encoder.position

        if mode == "main_menu":
            if pos > last_encoder_position:
                menu_index = (menu_index + 1) % len(menu_screens.MAIN_MENU_OPTIONS)
            elif pos < last_encoder_position:
                menu_index = (menu_index - 1) % len(menu_screens.MAIN_MENU_OPTIONS)

            menu_screens.show_main_menu(main_group, menu_index)

        elif mode == "difficulty":
            if pos > last_encoder_position:
                difficulty_index = (difficulty_index + 1) % len(
                    menu_screens.DIFFICULTY_OPTIONS
                )
            elif pos < last_encoder_position:
                difficulty_index = (difficulty_index - 1) % len(
                    menu_screens.DIFFICULTY_OPTIONS
                )

            menu_screens.show_difficulty_menu(main_group, difficulty_index)

        last_encoder_position = pos

    # ----- BUTTON (edge detect) -----
    current_button_state = button.value  # True = released, False = pressed
    if last_button_state and not current_button_state:
        # just pressed
        if mode == "main_menu":
            choice = menu_screens.MAIN_MENU_OPTIONS[menu_index]
            if choice == "Start Game":
                mode = "difficulty"
                # reset reference so encoder movement starts fresh
                last_encoder_position = encoder.position
                menu_screens.show_difficulty_menu(main_group, difficulty_index)
            else:  # Exit
                turn_off_display_and_exit()

        elif mode == "difficulty":
            selected_difficulty = menu_screens.DIFFICULTY_OPTIONS[difficulty_index]
            print("Difficulty selected:", selected_difficulty)  # REPL debug
            mode = "game"
            menu_screens.show_game_screen(main_group, selected_difficulty)

        elif mode == "game":
            # optional: button could return to main menu
            # mode = "main_menu"
            # last_encoder_position = encoder.position
            # menu_index = 0
            # menu_screens.show_main_menu(main_group, menu_index)
            pass

    last_button_state = current_button_state
    time.sleep(0.005)