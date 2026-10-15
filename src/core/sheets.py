"""Sprite sheets and frame data files (FR-4.7). No file or UI code here: this builds the images and the text."""
from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image

from . import blank_sheet
from .colour import Colour
from .project import Project

PER_ROW = 10                # a sheet holds 10 sprites per row, in boxes like a blank sprite sheet
SWATCH = 8                  # colour bar swatches are 8 x 8 pixels
SWATCH_GAP = 4              # space between colour bar swatches
NO_GROUP = "NoGroup"

FOLDER_SHEET = "Sprite_Sheet"
FOLDER_GROUP_SHEETS = "Frame_Sprite_Sheets"
FOLDER_SPRITES = "Sprites"
FOLDERS = (FOLDER_SHEET, FOLDER_GROUP_SHEETS, FOLDER_SPRITES)

BOX_CANDIDATES: tuple[Colour, ...] = ((0, 255, 0), (0, 255, 255), (255, 255, 0), (0, 0, 255), (255, 0, 0), (0, 128, 255),
                                      (255, 128, 0), (128, 255, 0), (0, 255, 128), (128, 0, 255), (255, 0, 128))


@dataclass
class Sheet:
    image: Image.Image
    positions: list[tuple[int, int, int]]      # (frame index, x, y) of each frame's top-left pixel
    box: Colour = (0, 255, 0)                   # the colour of the box lines


def box_colour(palette: list[Colour], fill: Colour) -> Colour:
    """The box line colour: green unless the sprites (or the fill) already use it, then the first free colour."""
    taken = set(palette) | {tuple(fill)}
    for c in BOX_CANDIDATES:
        if c not in taken:
            return c
    for v in range(255, -1, -1):                       # (cannot happen with at most 64 colours, but never fail)
        if (0, v, 255 - v) not in taken:
            return (0, v, 255 - v)
    return (0, 255, 0)


def layout(count: int) -> tuple[int, int]:
    """(sprites per row, rows) for `count` frames: 10 per row, fewer on a short sheet."""
    per = max(1, min(PER_ROW, count))
    return per, max(1, math.ceil(count / per))


def _bar_rows(width: int, colours: int) -> int:
    return math.ceil(colours / max(1, (width + SWATCH_GAP) // (SWATCH + SWATCH_GAP)))


def sheet_size(count: int, frame_w: int, frame_h: int, colours: int) -> tuple[int, int]:
    """Size of a sheet of `count` frames: the text bar, the boxes (1 px lines), and the colour bar underneath."""
    per, rows = layout(count)
    width, height = blank_sheet.sheet_size(frame_w, frame_h, per, rows)
    bar_rows = _bar_rows(width, colours)
    return width, height + SWATCH_GAP + bar_rows * SWATCH + (bar_rows - 1) * SWATCH_GAP


def build_sheet(project: Project, indices: list[int], fill: Colour) -> Sheet:
    """The frames in boxes, 10 to a row, in the same format as a blank sprite sheet (so it can be imported again),
    with the colour bar underneath. One source pixel is one pixel in the sheet; nothing is scaled."""
    w, h = project.width, project.height
    palette = project.palette()
    per, rows = layout(len(indices))
    box = box_colour(palette, fill)
    width, height = sheet_size(len(indices), w, h, len(palette))
    grid_h = blank_sheet.sheet_size(w, h, per, rows)[1]
    img = blank_sheet.build(project.system, w, h, per, rows, box, fill, title="sprite sheet", count=len(indices),
                            extra_height=height - grid_h)
    positions: list[tuple[int, int, int]] = []
    for n, idx in enumerate(indices):
        x = 1 + (n % per) * (w + 1)
        y = blank_sheet.BAR_H + 1 + (n // per) * (h + 1)
        img.paste(project.frames[idx].image, (x, y))
        positions.append((idx, x, y))
    per_row = max(1, (width + SWATCH_GAP) // (SWATCH + SWATCH_GAP))
    bar_y = grid_h + SWATCH_GAP
    for n, colour in enumerate(palette):
        x = (n % per_row) * (SWATCH + SWATCH_GAP)
        y = bar_y + (n // per_row) * (SWATCH + SWATCH_GAP)
        img.paste(Image.new("RGB", (SWATCH, SWATCH), colour), (x, y))
    return Sheet(img, positions, box)


def group_name_of(project: Project, index: int) -> str:
    for g in project.groups:
        if g.first <= index <= g.last:
            return g.name
    return ""


def frame_file_name(project: Project, index: int) -> str:
    """ProjectName_FrameGroup_FrameLabel.png, with NoGroup for a frame that is in no group."""
    return f"{project.name}_{group_name_of(project, index) or NO_GROUP}_{project.frames[index].label}.png"


def all_sheet_name(project: Project) -> str:
    return f"{project.name}_SpriteSheet.png"


def group_sheet_name(project: Project, group_name: str) -> str:
    return f"{project.name}_{group_name}_SpriteSheet.png"


def frame_data_text(project: Project, sheet_file: str, size: tuple[int, int], positions: list[tuple[int, int, int]]) -> str:
    """The frame data file saved next to a sheet (FR-4.7): header lines, a title line, one line per frame."""
    lines = [
        f"Project: {project.name}",
        f"System: {project.system.name}",
        f"FramesPerSecond: {project.fps}",
        f"FrameSize: {project.width} x {project.height}",
        f"SheetFile: {sheet_file}",
        f"SheetSize: {size[0]} x {size[1]}",
        "Number, Label, Group, X, Y, Width, Height",
    ]
    for idx, x, y in positions:
        lines.append(f"{idx + 1}, {project.frames[idx].label}, {group_name_of(project, idx)}, {x}, {y}, "
                     f"{project.width}, {project.height}")
    return "\n".join(lines) + "\n"
