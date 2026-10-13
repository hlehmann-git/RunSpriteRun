"""Sprite drawing with Pillow (section 5.1 Rendering): nearest-neighbour only, whole-number scales,
transparent colour shown as the black background, 1 px black grid in the last row and column of each cell."""
from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw
from PySide6.QtGui import QImage

from src.core.colour import Colour


def fit_scale(w: int, h: int, view_w: int, view_h: int) -> int:
    """Largest whole-number scale that fits the view (at least 1). No partial scales."""
    return max(1, min(view_w // w, view_h // h))


def hide_transparent(img: Image.Image, transparent: Colour) -> Image.Image:
    """Paint pixels of the transparent colour black."""
    r, g, b = img.split()
    mask = ImageChops.darker(
        ImageChops.darker(r.point(lambda v: 255 if v == transparent[0] else 0),
                          g.point(lambda v: 255 if v == transparent[1] else 0)),
        b.point(lambda v: 255 if v == transparent[2] else 0))
    return Image.composite(Image.new("RGB", img.size, (0, 0, 0)), img, mask)


def scaled_sprite(img: Image.Image, transparent: Colour, view_w: int, view_h: int, grid: bool) -> Image.Image:
    """The sprite at the largest whole-number scale that fits, with the grid if asked (scale 2 or more)."""
    w, h = img.size
    s = fit_scale(w, h, view_w, view_h)
    big = hide_transparent(img, transparent).resize((w * s, h * s), Image.NEAREST)
    if grid and s >= 2:
        d = ImageDraw.Draw(big)
        for k in range(1, w + 1):
            d.line([(k * s - 1, 0), (k * s - 1, h * s - 1)], fill=(0, 0, 0))
        for k in range(1, h + 1):
            d.line([(0, k * s - 1), (w * s - 1, k * s - 1)], fill=(0, 0, 0))
    return big


def render_sprite_at(img: Image.Image, transparent: Colour, view_w: int, view_h: int, scale: int) -> Image.Image:
    """A view image with the sprite centred at a given whole-number scale (the RunSpriteRun zoom), no grid.
    The scale never goes beyond what fits the view."""
    w, h = img.size
    s = max(1, min(scale, fit_scale(w, h, view_w, view_h)))
    big = hide_transparent(img, transparent).resize((w * s, h * s), Image.NEAREST)
    out = Image.new("RGB", (view_w, view_h), (0, 0, 0))
    out.paste(big, ((view_w - big.width) // 2, (view_h - big.height) // 2))
    return out


def render_window(img: Image.Image, transparent: Colour, view_w: int, view_h: int, scale: int, left: int, top: int,
                  grid: bool) -> Image.Image:
    """A view image of a zoomed sprite: the sprite at a whole-number scale with its top left corner at (left, top)
    in view pixels (it can be negative: the sprite is panned). Only the visible part is scaled. The grid is always
    1 px wide (scale 2 or more)."""
    w, h = img.size
    out = Image.new("RGB", (view_w, view_h), (0, 0, 0))
    x0, y0 = max(0, -left // scale), max(0, -top // scale)
    x1, y1 = min(w, (view_w - left) // scale + 1), min(h, (view_h - top) // scale + 1)
    if x1 <= x0 or y1 <= y0:
        return out
    part = hide_transparent(img.crop((x0, y0, x1, y1)), transparent).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST)
    if grid and scale >= 2:
        d = ImageDraw.Draw(part)
        for k in range(1, x1 - x0 + 1):
            d.line([(k * scale - 1, 0), (k * scale - 1, part.height - 1)], fill=(0, 0, 0))
        for k in range(1, y1 - y0 + 1):
            d.line([(0, k * scale - 1), (part.width - 1, k * scale - 1)], fill=(0, 0, 0))
    out.paste(part, (left + x0 * scale, top + y0 * scale))
    return out


def render_sprite(img: Image.Image, transparent: Colour, view_w: int, view_h: int, grid: bool) -> Image.Image:
    """A full view image (black background, sprite centred) at physical pixel size."""
    big = scaled_sprite(img, transparent, view_w, view_h, grid)
    out = Image.new("RGB", (view_w, view_h), (0, 0, 0))
    out.paste(big, ((view_w - big.width) // 2, (view_h - big.height) // 2))
    return out


def to_qimage(img: Image.Image, device_ratio: float = 1.0) -> QImage:
    """Pillow RGB image to a QImage that is drawn 1:1 in physical pixels."""
    qimg = QImage(img.tobytes(), img.width, img.height, 3 * img.width, QImage.Format_RGB888).copy()
    qimg.setDevicePixelRatio(device_ratio)
    return qimg
