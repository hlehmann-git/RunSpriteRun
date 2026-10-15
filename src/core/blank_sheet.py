"""Blank sprite sheet (FR-4.9): an empty picture with one bordered box for every sprite, to be filled in with
another art program. No file or UI code here: this builds the image and the text."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .colour import Colour
from .rules import MAX_FRAMES, MAX_SIZE, MIN_SIZE
from .systems import System

MAX_WIDTH = 2048             # the sheet is never wider than this (same as the sprite sheets, FR-4.7)
MIN_WIDTH = 640              # narrower sheets are widened so that the text bar can be read
BAR_H = 62                   # height of the text bar at the top
MARGIN = 6                   # space around the text
LINE_H = 11
BG: Colour = (224, 224, 224)           # text bar and any space beside the boxes
TEXT: Colour = (0, 0, 0)
DEFAULT_BOX: Colour = (0, 255, 0)      # the "not used" bounding box colour
DEFAULT_FILL: Colour = (255, 0, 255)   # inside of an empty box: magenta, the transparent colour
FOLDER = "Blank sprite sheets"

FOLDER_NAMES = {
    "Sega Master System": "Master_System",
    "Sega Genesis / Mega Drive": "Genesis_Megadrive",
    "Super Nintendo (SNES)": "SuperFamicom_SNES",
    "Atari ST": "Atari_ST",
    "Atari STE": "Atari_STE",
    "Amiga": "Amiga",
}

MSG_TOO_MANY = "A blank sprite sheet can hold at most 120 sprites and be 2,048 pixels wide."
MSG_SAME_COLOUR = "The box colour and the transparent colour must be different."


def system_folder(system: System) -> str:
    """Folder name of a system: its short name with underscores instead of spaces and symbols."""
    return FOLDER_NAMES.get(system.name) or "".join(c if c.isalnum() else "_" for c in system.name)


def file_name(system: System, w: int, h: int, per_row: int, rows: int) -> str:
    return f"BlankSheet_{system_folder(system)}_{w}x{h}_{per_row}x{rows}.png"


def sheet_size(w: int, h: int, per_row: int, rows: int) -> tuple[int, int]:
    """One 1 px line between neighbouring boxes and around the outside: per_row x (w + 1) + 1 pixels across."""
    return max(MIN_WIDTH, per_row * (w + 1) + 1), BAR_H + rows * (h + 1) + 1


def problem(w: int, h: int, per_row: int, rows: int, box: Colour, fill: Colour) -> str | None:
    """None if the settings can be made, otherwise the message to show."""
    if not (MIN_SIZE <= w <= MAX_SIZE and MIN_SIZE <= h <= MAX_SIZE and per_row >= 1 and rows >= 1):
        return MSG_TOO_MANY
    if per_row * rows > MAX_FRAMES or per_row * (w + 1) + 1 > MAX_WIDTH:
        return MSG_TOO_MANY
    if tuple(box) == tuple(fill):
        return MSG_SAME_COLOUR
    return None


def text_lines(system: System, w: int, h: int, per_row: int, rows: int, box: Colour, fill: Colour,
               title: str = "blank sprite sheet", count: int | None = None) -> list[str]:
    hexs = lambda c: "#%02X%02X%02X" % tuple(c)
    return [
        f"RunSpriteRun {title}: {system.name}",
        f"Colour depth: {system.depth_label}, {system.bits} bits per channel ({system.levels} levels). "
        f"{system.total_colours:,} colours available.",
        f"Palette limit: at most {system.max_colours} colours in all the sprites, including the transparent colour.",
        f"Sprites: {w} x {h} pixels, {per_row} per row, {rows} rows ({per_row * rows if count is None else count} sprites).",
        f"The {hexs(box)} lines are guides: do not use that colour in the sprites. "
        f"Empty boxes are {hexs(fill)}.",
    ]


def build(system: System, w: int, h: int, per_row: int, rows: int, box: Colour = DEFAULT_BOX,
          fill: Colour = DEFAULT_FILL, title: str = "blank sprite sheet", count: int | None = None,
          extra_height: int = 0) -> Image.Image:
    """The sheet: a text bar on top, then the grid of boxes. The inside of each box is exactly w x h pixels."""
    width, height = sheet_size(w, h, per_row, rows)
    img = Image.new("RGB", (width, height + extra_height), BG)       # extra_height: room under the boxes (colour bar)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=10)
    for n, line in enumerate(text_lines(system, w, h, per_row, rows, box, fill, title, count)):
        draw.text((MARGIN, MARGIN - 2 + n * LINE_H), line, fill=TEXT, font=font)
    grid_w, grid_h = per_row * (w + 1) + 1, rows * (h + 1) + 1
    draw.rectangle((0, BAR_H, grid_w - 1, BAR_H + grid_h - 1), fill=box)
    for r in range(rows):
        for c in range(per_row):
            x, y = 1 + c * (w + 1), BAR_H + 1 + r * (h + 1)
            draw.rectangle((x, y, x + w - 1, y + h - 1), fill=fill)
    return img
