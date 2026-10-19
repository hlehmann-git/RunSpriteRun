"""Shrink sprite (Edit menu): every frame of the open project is made smaller by a fixed percentage of its size.
Pixels are averaged, then each one is snapped to the nearest colour the project already uses, so the project never
gets a colour it did not have and stays inside the system's colour limit. No UI code here."""
from __future__ import annotations

from PIL import Image

from .colour import Colour
from . import layers as layer_rules
from .project import Project
from .rules import MIN_SIZE

SHRINK_PERCENTS = (87.5, 75, 50, 25, 12.5)        # the size of the result as a percentage of the original size
MSG_TOO_SMALL = f"The sprite would be smaller than {MIN_SIZE} pixels."


def percent_label(pct: float) -> str:
    return f"{pct:g}%"


def new_size(width: int, height: int, pct: float) -> tuple[int, int]:
    """The size after shrinking: each side rounded to the nearest whole pixel (halves go up)."""
    return int(width * pct / 100 + 0.5), int(height * pct / 100 + 0.5)


def can_shrink(width: int, height: int, pct: float) -> bool:
    w, h = new_size(width, height, pct)
    return w >= MIN_SIZE and h >= MIN_SIZE and (w, h) != (width, height)


class _Table(dict):
    """(r, g, b, a) of an averaged pixel -> the three bytes of the colour it becomes."""

    def __init__(self, palette: list[Colour], transparent: Colour) -> None:
        super().__init__()
        self.palette = palette
        self.transparent = bytes(transparent)

    def __missing__(self, key):
        r, g, b, a = key
        if a < 128 or not self.palette:
            out = self.transparent
        else:
            best = min(self.palette, key=lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2)
            out = bytes(best)
        self[key] = out
        return out


def _shrink_image(img: Image.Image, size: tuple[int, int], transparent: Colour, table: _Table) -> Image.Image:
    """Average the pixels (transparent ones count as empty, not as a colour), then snap to the palette."""
    data = img.tobytes()
    t = tuple(transparent)
    alpha = bytes(0 if (data[i], data[i + 1], data[i + 2]) == t else 255 for i in range(0, len(data), 3))
    rgba = Image.merge("RGBA", (*img.split(), Image.frombytes("L", img.size, alpha)))
    small = rgba.resize(size, Image.BOX)
    sd = small.tobytes()
    out = b"".join(table[k] for k in zip(sd[0::4], sd[1::4], sd[2::4], sd[3::4]))
    return Image.frombytes("RGB", size, out)


def shrink_project(project: Project, pct: float) -> tuple[int, int]:
    """Shrink every frame (and each of its three layers) to `pct` percent of its size. Returns the new size. The project
    is changed in place and marked as unsaved. Raises ValueError if the result would be too small."""
    if not can_shrink(project.width, project.height, pct):
        raise ValueError(MSG_TOO_SMALL)
    size = new_size(project.width, project.height, pct)
    palette = [c for c in project.palette() if c != project.transparent]
    table = _Table(palette, project.transparent)
    for f in project.frames:
        if f.layers is not None:
            layers = tuple(_shrink_image(im, size, project.transparent, table) for im in f.layers)
            layer_rules.set_layers(f, layers, project.transparent)
        else:
            f.image = _shrink_image(f.image, size, project.transparent, table)
    project.width, project.height = size
    project.dirty = True
    return size
