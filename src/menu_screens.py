# menu_screens.py
import displayio
import terminalio
from adafruit_display_text import label

MAIN_MENU_OPTIONS = ["Start Game", "Exit"]
DIFFICULTY_OPTIONS = ["Easy", "Medium", "Hard"]
GAME_OVER_OPTIONS = ["Restart", "Main Menu"]


def clear_group(group: displayio.Group) -> None:
    while len(group):
        group.pop()


def show_splash_screen(group: displayio.Group) -> None:
    """Shown once when system boots."""
    clear_group(group)
    title = label.Label(
        terminalio.FONT,
        text="Welcome to",
        x=20,
        y=18,
    )
    title2 = label.Label(
        terminalio.FONT,
        text="Dodge Game",
        x=18,
        y=34,
    )
    group.append(title)
    group.append(title2)


def show_main_menu(group: displayio.Group, selected_index: int) -> None:
    clear_group(group)

    title = label.Label(terminalio.FONT, text="Main Menu", x=28, y=10)
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
            y=y_positions[i],
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
            y=y_base + i * spacing,
        )
        group.append(item)


def show_game_over_menu(group: displayio.Group, selected_index: int) -> None:
    clear_group(group)

    title = label.Label(terminalio.FONT, text="Game Over", x=28, y=10)
    subtitle = label.Label(terminalio.FONT, text="Rotate + press", x=16, y=22)
    group.append(title)
    group.append(subtitle)

    y_base = 40
    spacing = 12
    for i, option in enumerate(GAME_OVER_OPTIONS):
        prefix = "> " if i == selected_index else "  "
        item = label.Label(
            terminalio.FONT,
            text=prefix + option,
            x=10,
            y=y_base + i * spacing,
        )
        group.append(item)
