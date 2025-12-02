# menu_screens.py
import displayio
import terminalio
from adafruit_display_text import label

MAIN_MENU_OPTIONS = ["Start Game", "Exit"]
DIFFICULTY_OPTIONS = ["Easy", "Medium", "Hard"]


def clear_group(group: displayio.Group) -> None:
    while len(group):
        group.pop()


def show_main_menu(group: displayio.Group, selected_index: int) -> None:
    clear_group(group)

    title = label.Label(terminalio.FONT, text="Welcome!", x=28, y=10)
    subtitle = label.Label(terminalio.FONT, text="Rotate + press", x=16, y=22)
    group.append(title)
    group.append(subtitle)

    y_positions = [40, 52]
    for i, option in enumerate(MAIN_MENU_OPTIONS):
        prefix = "> " if i == selected_index else "  "
        item = label.Label(
            terminalio.FONT,
            text=prefix + option,
            x=10,
            y=y_positions[i]
        )
        group.append(item)


def show_difficulty_menu(group: displayio.Group, selected_index: int) -> None:
    clear_group(group)

    title = label.Label(terminalio.FONT, text="Select Difficulty", x=4, y=10)
    subtitle = label.Label(terminalio.FONT, text="Rotate + press", x=16, y=22)
    group.append(title)
    group.append(subtitle)

    y_base = 38
    spacing = 10
    for i, option in enumerate(DIFFICULTY_OPTIONS):
        prefix = "> " if i == selected_index else "  "
        item = label.Label(
            terminalio.FONT,
            text=prefix + option,
            x=10,
            y=y_base + i * spacing
        )
        group.append(item)


def show_game_screen(group: displayio.Group, difficulty: str) -> None:
    clear_group(group)
    title = label.Label(terminalio.FONT, text="Game Mode", x=24, y=16)
    text = label.Label(
        terminalio.FONT,
        text=difficulty,      # prints Easy / Medium / Hard
        x=40,
        y=36
    )
    group.append(title)
    group.append(text)