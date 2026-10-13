"""Sprite sheets and frame data files (FR-4.7). No file or UI code here: this builds the images and the text."""
from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image

from .colour import Colour
from .project import Project

SHEET_MAX_W = 2048          # a sheet wraps to a new row before it would be wider than this
SWATCH = 8                  # colour bar swatches are 8 x 8 pixels
NO_GROUP = "NoGroup"

FOLDER_SHEET = "Sprite_Sheet"
FOLDER_GROUP_SHEETS = "Frame_Sprite_Sheets"
FOLDER_SPRITES = "Sprites"
FOLDERS = (FOLDER_SHEET, FOLDER_GROUP_SHEETS, FOLDER_SPRITES)


@dataclass
class Sheet:
    image: Image.Image
    positions: list[tuple[int, int, int]]      # (frame index, x, y) of each frame's top-left pixel


def frames_per_row(frame_w: int, gap: int) -> int:
    """(2,048 + gap) divided by (frame width + gap), rounded down: 30 for 64 x 64 at gap 4, 256 for 4 x 4."""
    return max(1, (SHEET_MAX_W + gap) // (frame_w + gap))


def sheet_size(count: int, frame_w: int, frame_h: int, gap: int, colours: int) -> tuple[int, int]:
    """Size of a sheet of `count` frames, colour bar included."""
    per = frames_per_row(frame_w, gap)
    cols = min(count, per)
    rows = math.ceil(count / per)
    width = max(SWATCH, cols * frame_w + (cols - 1) * gap)
    frames_h = rows * frame_h + (rows - 1) * gap
    bar_rows = math.ceil(colours / max(1, (width + gap) // (SWATCH + gap)))
    bar_h = bar_rows * SWATCH + (bar_rows - 1) * gap
    return width, frames_h + gap + bar_h


def build_sheet(project: Project, indices: list[int], gap: int, fill: Colour) -> Sheet:
    """Frames left to right, wrapping at 2,048 pixels, with the colour bar underneath. One source pixel is one
    pixel in the sheet; nothing is scaled. Everything that is not a frame or a swatch is the fill colour."""
    w, h = project.width, project.height
    palette = project.palette()
    width, height = sheet_size(len(indices), w, h, gap, len(palette))
    img = Image.new("RGB", (width, height), fill)
    per = frames_per_row(w, gap)
    positions: list[tuple[int, int, int]] = []
    for n, idx in enumerate(indices):
        x = (n % per) * (w + gap)
        y = (n // per) * (h + gap)
        img.paste(project.frames[idx].image, (x, y))
        positions.append((idx, x, y))
    rows = math.ceil(len(indices) / per)
    bar_y = rows * h + (rows - 1) * gap + gap
    per_row = max(1, (width + gap) // (SWATCH + gap))
    for n, colour in enumerate(palette):
        x = (n % per_row) * (SWATCH + gap)
        y = bar_y + (n // per_row) * (SWATCH + gap)
        img.paste(Image.new("RGB", (SWATCH, SWATCH), colour), (x, y))
    return Sheet(img, positions)


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
