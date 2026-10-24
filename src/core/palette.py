"""Palette editing (FR-3.13): replace a colour everywhere, merge duplicates, the transparent colour,
and the geometry of the colour square. No UI code here."""
from __future__ import annotations

import colorsys

from PIL import Image

from .colour import Colour, channel_values, level_to_8bit, snap_colour, to_level
from . import layers as layer_rules
from .project import Project
from .systems import System

SQUARE = 128


def remap_image(img: Image.Image, old: Colour, new: Colour) -> Image.Image:
    """A copy of the RGB image `img` with every pixel of colour `old` changed to `new`. The same image comes back
    when it has no pixel of `old`, so earlier states (undo) keep their own images."""
    old, new = tuple(old), tuple(new)
    data = img.tobytes()
    out = bytearray(data)
    changed = False
    for i in range(0, len(data), 3):
        if (data[i], data[i + 1], data[i + 2]) == old:
            out[i:i + 3] = bytes(new)
            changed = True
    return Image.frombytes("RGB", img.size, bytes(out)) if changed else img


def replace_colour(project: Project, old: Colour, new: Colour) -> None:
    """Every pixel of colour `old` becomes `new` (snapped to the system). New image objects are made so
    that earlier states (undo) keep their own images. If `old` was the transparent colour the transparent
    colour becomes `new`: the slot stays transparent."""
    new = project.system.snap(new)
    if new == old:
        return
    def remap(img):
        return remap_image(img, old, new)

    for f in project.frames:
        f.image = remap(f.image)
        if f.layers is not None:
            f.layers = tuple(remap(im) for im in f.layers)
    project.extra_colours = [new if c == old else c for c in project.extra_colours]
    if project.transparent == old:
        project.transparent = new
    for f in project.frames:
        layer_rules.refresh(f, project.transparent)       # a merge can make a colour see-through


def set_transparent(project: Project, colour: Colour) -> None:
    project.transparent = colour
    for f in project.frames:
        layer_rules.refresh(f, colour)


def is_duplicate(project: Project, slot: int, new: Colour) -> bool:
    """True if `new` (snapped) is already in the palette in a different slot."""
    colours = project.palette()
    new = project.system.snap(new)
    return new in colours and colours[slot] != new


# ---- colour square (FR-3.13) ----------------------------------------------------------------------
def _tile_layout(system: System) -> tuple[int, int, int, int, int]:
    """(tile columns, tile rows, blocks per tile side, block w, block h) for tiled systems."""
    return {2: (2, 2, 4, 16, 16), 3: (4, 2, 8, 4, 8), 4: (4, 4, 16, 2, 2)}[system.bits]


def _is_stepped(system: System) -> bool:
    return system.bits == 5


def _snes_cell(x: int, y: int) -> Colour:
    col, row = x // 2, y // 4                  # 64 hue columns x 32 brightness rows
    hue = col / 64
    light = 1 - row / 31                      # top row white, bottom row black
    r, g, b = colorsys.hls_to_rgb(hue, light, 1.0)
    return snap_colour((round(r * 255), round(g * 255), round(b * 255)), 5)


def colour_at(system: System, x: int, y: int) -> Colour:
    """The colour under a point of the 128 x 128 square."""
    x = max(0, min(SQUARE - 1, x))
    y = max(0, min(SQUARE - 1, y))
    if _is_stepped(system):
        return _snes_cell(x, y)
    tc, tr, side, bw, bh = _tile_layout(system)
    tw, th = side * bw, side * bh
    blue = (y // th) * tc + (x // tw)
    red = (x % tw) // bw
    green = (y % th) // bh
    bits = system.bits
    return (level_to_8bit(red, bits), level_to_8bit(green, bits), level_to_8bit(blue, bits))


def square_image(system: System) -> Image.Image:
    img = Image.new("RGB", (SQUARE, SQUARE))
    px = img.load()
    if _is_stepped(system):
        cache = {}
        for y in range(SQUARE):
            for x in range(SQUARE):
                k = (x // 2, y // 4)
                if k not in cache:
                    cache[k] = _snes_cell(x, y)
                px[x, y] = cache[k]
    else:
        for y in range(SQUARE):
            for x in range(SQUARE):
                px[x, y] = colour_at(system, x, y)
    return img


def marker_rect(system: System, colour: Colour, hint: tuple[int, int] | None = None) -> tuple[int, int, int, int] | None:
    """(x, y, w, h) of the square cell holding `colour`. In the SNES square several cells can hold the
    same colour; the one nearest `hint` (the last point clicked) is used."""
    colour = system.snap(colour)
    if _is_stepped(system):
        hx, hy = hint if hint is not None else (0, 0)
        best, best_d = None, None
        for row in range(32):
            for col in range(64):
                if _snes_cell(col * 2, row * 4) == colour:
                    d = (col * 2 - hx) ** 2 + (row * 4 - hy) ** 2
                    if best_d is None or d < best_d:
                        best, best_d = (col * 2, row * 4, 2, 4), d
        return best
    tc, tr, side, bw, bh = _tile_layout(system)
    bits = system.bits
    r, g, b = (to_level(v, bits) for v in colour)
    tw, th = side * bw, side * bh
    return ((b % tc) * tw + r * bw, (b // tc) * th + g * bh, bw, bh)
