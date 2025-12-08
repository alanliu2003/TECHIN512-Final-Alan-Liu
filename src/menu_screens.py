# menu_screens.py
import displayio
import terminalio
from adafruit_display_text import label

MAIN_MENU_OPTIONS = ["Start Game", "Exit"]
DIFFICULTY_OPTIONS = ["Easy", "Medium", "Hard"]
GAME_OVER_OPTIONS = ["Restart", "Main Menu"]

LEVEL_COUNT = 10  # 10 levels per difficulty


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


def show_level_menu(
    group: displayio.Group,
    difficulty_name: str,
    level_index: int,
) -> None:
    """
    Level select screen for given difficulty.
    level_index is 0-based (0..9), display as Level 1..10.
    """
    clear_group(group)

    title_text = "{} Levels".format(difficulty_name)
    title = label.Label(terminalio.FONT, text=title_text, x=12, y=12)
    group.append(title)

    subtitle = label.Label(
        terminalio.FONT,
        text="Rotate to choose",
        x=8,
        y=26,
    )
    group.append(subtitle)

    level_num = level_index + 1
    level_text = "> Level {}/{}".format(level_num, LEVEL_COUNT)
    level_label = label.Label(
        terminalio.FONT,
        text=level_text,
        x=16,
        y=44,
    )
    group.append(level_label)

    hint = label.Label(
        terminalio.FONT,
        text="Press to start",
        x=20,
        y=56,
    )
    group.append(hint)


def show_name_entry(
    group: displayio.Group,
    current_name: str,
    current_char: str,
) -> None:
    """Name entry screen shown after level select."""
    clear_group(group)

    title = label.Label(terminalio.FONT, text="Enter Name", x=18, y=10)
    group.append(title)

    name_label = label.Label(
        terminalio.FONT,
        text="Name: {}".format(current_name),
        x=4,
        y=26,
    )
    group.append(name_label)

    char_label = label.Label(
        terminalio.FONT,
        text="Char: [{}]".format(current_char),
        x=4,
        y=40,
    )
    group.append(char_label)

    hint1 = label.Label(
        terminalio.FONT,
        text="Left/Right: change",
        x=4,
        y=52,
    )
    group.append(hint1)


def show_game_over_menu(
    group: displayio.Group,
    selected_index: int,
    player_score: int,
    high_scores: list,
) -> None:
    clear_group(group)

    title = label.Label(terminalio.FONT, text="Game Over", x=28, y=8)
    group.append(title)

    your_line = label.Label(
        terminalio.FONT,
        text="You: {}".format(player_score),
        x=4,
        y=18,
    )
    group.append(your_line)

    hs_title = label.Label(
        terminalio.FONT,
        text="High Scores:",
        x=4,
        y=28,
    )
    group.append(hs_title)

    # Show up to top 5 scores for this level
    y_base = 36
    spacing = 8
    for i, entry in enumerate(high_scores[:5]):
        name = entry.get("name", "")[:5]  # shorten long names
        score = entry.get("score", 0)
        line_text = "{}. {} {}".format(i + 1, name, score)
        line = label.Label(
            terminalio.FONT,
            text=line_text,
            x=4,
            y=y_base + i * spacing,
        )
        group.append(line)

    # Menu options (Restart / Main Menu) near bottom
    y_menu_base = 56  # last visible row
    # Put them compact on the right side
    for i, option in enumerate(GAME_OVER_OPTIONS):
        prefix = "> " if i == selected_index else "  "
        item = label.Label(
            terminalio.FONT,
            text=prefix + option,
            x=70,
            y=y_menu_base - (1 - i) * 8,  # Restart on line above Main Menu
        )
        group.append(item)

