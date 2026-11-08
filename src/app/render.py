"""Sprite drawing with Pillow (section 5.1 Rendering): nearest-neighbour only, whole-number scales,
transparent colour shown as the black background, 1 px black grid in the last row and column of each cell.
v2.0.19: the larger views can show the transparent colour as a checkerboard (display only, files are unchanged)."""
from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw
from PySide6.QtGui import QImage

from src.core.colour import Colour


CHECKER_LIGHT, CHECKER_DARK = (192, 192, 192), (128, 128, 128)
CHECKER_CELL = 3                       # each checkerboard square covers 3 x 3 sprite pixels, at any zoom
GRID_ON_CHECKER = (104, 104, 104)      # grid lines over the checkerboard: softer than black so they do not clash
GRID = (0, 0, 0)


def transparent_mask(img: Image.Image, transparent: Colour) -> Image.Image:
    """An L image: 255 where the pixel is the transparent colour, 0 elsewhere."""
    r, g, b = img.convert("RGB").split()
    return ImageChops.darker(
        ImageChops.darker(r.point(lambda v: 255 if v == transparent[0] else 0),
                          g.point(lambda v: 255 if v == transparent[1] else 0)),
        b.point(lambda v: 255 if v == transparent[2] else 0))


def checker_pattern(w: int, h: int, left: int = 0, top: int = 0) -> Image.Image:
    """The checkerboard at sprite-pixel size for a w x h area whose top left is sprite pixel (left, top), so the
    squares stay in the same place on the sprite however it is cropped or zoomed."""
    n = CHECKER_CELL
    tile = Image.new("RGB", (2 * n, 2 * n), CHECKER_LIGHT)
    tile.paste(CHECKER_DARK, (n, 0, 2 * n, n))
    tile.paste(CHECKER_DARK, (0, n, n, 2 * n))
    ox, oy = left % (2 * n), top % (2 * n)
    big = Image.new("RGB", (w + ox + 2 * n, h + oy + 2 * n))
    for y in range(0, big.height, 2 * n):
        for x in range(0, big.width, 2 * n):
            big.paste(tile, (x, y))
    return big.crop((ox, oy, ox + w, oy + h))


def with_checker(big: Image.Image, img: Image.Image, transparent: Colour, scale: int, left: int = 0,
                 top: int = 0) -> Image.Image:
    """big is img scaled by scale (nearest neighbour). Its transparent pixels become the checkerboard."""
    mask = transparent_mask(img, transparent)
    if not mask.getbbox():
        return big
    pattern = checker_pattern(img.width, img.height, left, top).resize(big.size, Image.NEAREST)
    return Image.composite(pattern, big, mask.resize(big.size, Image.NEAREST))


def draw_grid(big: Image.Image, cols: int, rows: int, scale: int, soft: Image.Image | None = None) -> None:
    """The 1 px grid in the last row and column of each cell. soft (an L mask at sprite-pixel size): cells that show
    the checkerboard, whose grid lines are drawn softer."""
    d = ImageDraw.Draw(big)
    for k in range(1, cols + 1):
        d.line([(k * scale - 1, 0), (k * scale - 1, big.height - 1)], fill=GRID)
    for k in range(1, rows + 1):
        d.line([(0, k * scale - 1), (big.width - 1, k * scale - 1)], fill=GRID)
    if soft is None or not soft.getbbox():
        return
    lines = Image.new("L", big.size, 0)
    d = ImageDraw.Draw(lines)
    for k in range(1, cols + 1):
        d.line([(k * scale - 1, 0), (k * scale - 1, big.height - 1)], fill=255)
    for k in range(1, rows + 1):
        d.line([(0, k * scale - 1), (big.width - 1, k * scale - 1)], fill=255)
    big.paste(GRID_ON_CHECKER, (0, 0), ImageChops.multiply(lines, soft.resize(big.size, Image.NEAREST)))


def fit_scale(w: int, h: int, view_w: int, view_h: int) -> int:
    """Largest whole-number scale that fits the view (at least 1). No partial scales."""
    return max(1, min(view_w // w, view_h // h))


def fit_scale_fractional(w: int, h: int, view_w: int, view_h: int) -> float:
    """Largest scale, whole or fractional, that fits the view. For small reference thumbnails only (never for a
    pixel-editing view), so a canvas size that lands between two whole-number scales still fills its box."""
    return min(view_w / w, view_h / h)


def hide_transparent(img: Image.Image, transparent: Colour) -> Image.Image:
    """Paint pixels of the transparent colour black."""
    return Image.composite(Image.new("RGB", img.size, (0, 0, 0)), img, transparent_mask(img, transparent))


def scaled_sprite(img: Image.Image, transparent: Colour, view_w: int, view_h: int, grid: bool,
                  hide: bool = False, checker: bool = False) -> Image.Image:
    """The sprite at the largest whole-number scale that fits, with the grid if asked (scale 2 or more). The
    transparent colour is shown as itself (it marks the frame size); hide=True paints it black (timeline boxes);
    checker=True shows it as the checkerboard."""
    w, h = img.size
    s = fit_scale(w, h, view_w, view_h)
    big = (hide_transparent(img, transparent) if hide else img).resize((w * s, h * s), Image.NEAREST)
    checker = checker and not hide
    if checker:
        big = with_checker(big, img, transparent, s)
    if grid and s >= 2:
        draw_grid(big, w, h, s, transparent_mask(img, transparent) if checker else None)
    return big


def render_sprite_at(img: Image.Image, transparent: Colour, view_w: int, view_h: int, scale: int,
                     checker: bool = False) -> Image.Image:
    """A view image with the sprite centred at a given whole-number scale (the RunSpriteRun zoom), no grid.
    The scale never goes beyond what fits the view."""
    w, h = img.size
    s = max(1, min(scale, fit_scale(w, h, view_w, view_h)))
    big = img.resize((w * s, h * s), Image.NEAREST)
    if checker:
        big = with_checker(big, img, transparent, s)
    out = Image.new("RGB", (view_w, view_h), (0, 0, 0))
    out.paste(big, ((view_w - big.width) // 2, (view_h - big.height) // 2))
    return out


def render_window(img: Image.Image, transparent: Colour, view_w: int, view_h: int, scale: int, left: int, top: int,
                  grid: bool, checker: bool = False) -> Image.Image:
    """A view image of a zoomed sprite: the sprite at a whole-number scale with its top left corner at (left, top)
    in view pixels (it can be negative: the sprite is panned). Only the visible part is scaled. The grid is always
    1 px wide (scale 2 or more)."""
    w, h = img.size
    out = Image.new("RGB", (view_w, view_h), (0, 0, 0))
    x0, y0 = max(0, -left // scale), max(0, -top // scale)
    x1, y1 = min(w, (view_w - left) // scale + 1), min(h, (view_h - top) // scale + 1)
    if x1 <= x0 or y1 <= y0:
        return out
    crop = img.crop((x0, y0, x1, y1))
    part = crop.resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST)
    if checker:
        part = with_checker(part, crop, transparent, scale, x0, y0)
    if grid and scale >= 2:
        draw_grid(part, x1 - x0, y1 - y0, scale, transparent_mask(crop, transparent) if checker else None)
    out.paste(part, (left + x0 * scale, top + y0 * scale))
    return out


def render_sprite(img: Image.Image, transparent: Colour, view_w: int, view_h: int, grid: bool,
                  checker: bool = False) -> Image.Image:
    """A full view image (black background, sprite centred) at physical pixel size."""
    big = scaled_sprite(img, transparent, view_w, view_h, grid, checker=checker)
    out = Image.new("RGB", (view_w, view_h), (0, 0, 0))
    out.paste(big, ((view_w - big.width) // 2, (view_h - big.height) // 2))
    return out


def render_sprite_smooth(img: Image.Image, transparent: Colour, view_w: int, view_h: int,
                         checker: bool = False) -> Image.Image:
    """A full view image at a fractional scale that always fills the box, with smooth (not nearest-neighbour)
    resampling. For small reference thumbnails (section 5.1 exempts these: pixel accuracy does not matter at
    this size, and a sprite whose height falls between two whole-number scales should not look tiny)."""
    w, h = img.size
    s = fit_scale_fractional(w, h, view_w, view_h)
    big = img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    if checker:
        big = with_checker(big, img, transparent, s)
    out = Image.new("RGB", (view_w, view_h), (0, 0, 0))
    out.paste(big, ((view_w - big.width) // 2, (view_h - big.height) // 2))
    return out


def to_qimage(img: Image.Image, device_ratio: float = 1.0) -> QImage:
    """Pillow RGB image to a QImage that is drawn 1:1 in physical pixels."""
    qimg = QImage(img.tobytes(), img.width, img.height, 3 * img.width, QImage.Format_RGB888).copy()
    qimg.setDevicePixelRatio(device_ratio)
    return qimg
