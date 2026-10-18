"""Editing a frame's layers (V2.0). Pure logic with no UI. Images are never changed in place: every edit makes new
images, so Undo can keep the old ones."""
from __future__ import annotations

from PIL import Image

from . import layers as L
from .colour import Colour
from .project import Frame, Project


def paint(base_layers, targets, points, colour: Colour, size) -> tuple:
    """New layers with `points` painted `colour` on each target layer (clipped to the frame)."""
    w, h = size
    out = list(base_layers)
    inside = [(x, y) for x, y in points if 0 <= x < w and 0 <= y < h]
    for i in targets:
        im = out[i].copy()
        for p in inside:
            im.putpixel(p, tuple(colour))
        out[i] = im
    return tuple(out)


def shifted(base_layers, targets, dx: int, dy: int, transparent: Colour) -> tuple:
    """New layers with each target layer moved by dx, dy. What leaves the frame is cut off and the space left
    behind is the transparent colour; nothing wraps round."""
    out = list(base_layers)
    for i in targets:
        src = out[i]
        im = L.blank(src.size, transparent)
        im.paste(src, (dx, dy))
        out[i] = im
    return tuple(out)


def flip_horizontal(base, targets):
    return _each(base, targets, lambda im: im.transpose(Image.FLIP_LEFT_RIGHT))


def flip_vertical(base, targets):
    return _each(base, targets, lambda im: im.transpose(Image.FLIP_TOP_BOTTOM))


def rotate(base, targets, clockwise: bool):
    return _each(base, targets, lambda im: im.transpose(Image.ROTATE_270 if clockwise else Image.ROTATE_90))


# ---- rectangle selections ---------------------------------------------------------------------------------
def crop_layers(base, targets, rect) -> dict:
    """The pixels of `rect` (x0, y0, x1, y1) on each target layer, as a {layer index: image} copy."""
    return {i: base[i].crop(rect) for i in targets}


def clear_rect(base, targets, rect, transparent: Colour) -> tuple:
    """New layers with `rect` cleared to the transparent colour on each target layer."""
    out = list(base)
    for i in targets:
        im = out[i].copy()
        im.paste(tuple(transparent), rect)
        out[i] = im
    return tuple(out)


def paste_layers(base, clip: dict, x: int, y: int, transparent: Colour) -> tuple:
    """New layers with the clipboard pixels placed at (x, y) on the layers they came from. The transparent
    colour is see-through; what falls outside the frame is cut off."""
    out = list(base)
    for i, im in clip.items():
        dest = out[i].copy()
        dest.paste(im, (x, y), L.opaque_mask(im, transparent))
        out[i] = dest
    return tuple(out)


def shifted_region(base, targets, rect, dx: int, dy: int, transparent: Colour) -> tuple:
    """New layers with the pixels of `rect` moved by dx, dy on each target layer: the space they leave is the
    transparent colour, the moved pixels cover what they land on (their own transparent pixels do not)."""
    return paste_layers(clear_rect(base, targets, rect, transparent), crop_layers(base, targets, rect),
                        rect[0] + dx, rect[1] + dy, transparent)


def region_each(base, targets, rect, fn) -> tuple:
    """New layers with fn (a same-size image change, such as a flip) applied inside `rect` on each target layer."""
    out = list(base)
    for i in targets:
        im = out[i].copy()
        im.paste(fn(im.crop(rect)), rect[:2])
        out[i] = im
    return tuple(out)


def _each(base, targets, fn):
    out = list(base)
    for i in targets:
        out[i] = fn(out[i])
    return tuple(out)


def apply(project: Project, index: int, new_layers) -> bool:
    """Put new layers on frame `index`. Returns True if the picture of any layer changed."""
    f: Frame = project.frames[index]
    old = L.layers_of(f, project.transparent)
    if all(a.tobytes() == b.tobytes() for a, b in zip(old, new_layers)):
        return False
    L.set_layers(f, new_layers, project.transparent)
    return True


def set_frame_layers(project: Project, index: int, layers) -> None:
    """Show `layers` on a frame without comparing (used while a stroke is still being drawn)."""
    L.set_layers(project.frames[index], layers, project.transparent)


def can_add_colour(project: Project, colour: Colour) -> bool:
    return (not project.system.is_fixed and colour not in project.palette()
            and len(project.palette()) < project.system.max_colours)


def add_colour(project: Project, colour: Colour) -> bool:
    if not can_add_colour(project, colour):
        return False
    project.extra_colours.append(tuple(colour))
    return True
