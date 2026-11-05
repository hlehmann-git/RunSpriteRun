"""Resize Canvas (Edit menu, v2.0.20): every frame and every layer gets a new canvas size. Nothing is scaled: the sprite
keeps its pixels and is placed centred, or grounded (its bottom edge stays where it is). New space is filled with the
transparent colour. A canvas can never be made smaller than the sprites already drawn. No UI code here."""
from __future__ import annotations

from PIL import Image, ImageChops

from .colour import Colour
from .project import Project
from .rules import MAX_SIZE, MIN_SIZE

MSG_CLIPS = "This would cut off pixels in {n} of {total} frames. Choose a size of at least {w} x {h}."


def offset(old: int, new: int, grounded: bool = False) -> int:
    """Where the old picture's first column (or row) lands on the new canvas. Centred, the spare pixel of an odd
    difference goes on the right (or bottom), whether the canvas grows or shrinks; grounded (heights only) keeps the
    bottom edge, so all of the change is at the top."""
    if grounded:
        return new - old
    return (new - old) // 2 if new >= old else -((old - new) // 2)


def place(img: Image.Image, width: int, height: int, transparent: Colour, grounded: bool) -> Image.Image:
    out = Image.new("RGB", (width, height), transparent)
    out.paste(img, (offset(img.width, width), offset(img.height, height, grounded)))
    return out


def _drawn_box(img: Image.Image, transparent: Colour):
    """The smallest box holding every pixel that is not the transparent colour, or None if there are none."""
    key = Image.new("RGB", img.size, transparent)
    return ImageChops.difference(img.convert("RGB"), key).getbbox()


def drawn_boxes(project: Project) -> list:
    """One box per frame: everything drawn on it, on every layer (a pixel hidden under another layer still counts)."""
    out = []
    for f in project.frames:
        boxes = [b for b in (_drawn_box(im, project.transparent) for im in (f.image, *(f.layers or ()))) if b]
        out.append((min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
                    max(b[3] for b in boxes)) if boxes else None)
    return out


def _cuts(box, old_w: int, old_h: int, width: int, height: int, grounded: bool) -> bool:
    if box is None:
        return False
    x, y = offset(old_w, width), offset(old_h, height, grounded)
    return box[0] + x < 0 or box[1] + y < 0 or box[2] + x > width or box[3] + y > height


def clipped_frames(project: Project, width: int, height: int, grounded: bool, boxes=None) -> list[int]:
    """The frames (0-based) that would lose drawn pixels at this size."""
    boxes = drawn_boxes(project) if boxes is None else boxes
    return [i for i, b in enumerate(boxes) if _cuts(b, project.width, project.height, width, height, grounded)]


def smallest_size(project: Project, grounded: bool, boxes=None) -> tuple[int, int]:
    """The smallest width and height that keep every frame whole (never below the minimum frame size)."""
    boxes = drawn_boxes(project) if boxes is None else boxes
    w, h = project.width, project.height
    min_w = next(n for n in range(MIN_SIZE, w + 1) if not any(_cuts(b, w, h, n, h, grounded) for b in boxes))
    min_h = next(n for n in range(MIN_SIZE, h + 1) if not any(_cuts(b, w, h, w, n, grounded) for b in boxes))
    return min_w, min_h


def problem(project: Project, width: int, height: int, grounded: bool, boxes=None) -> str | None:
    """Why this size cannot be used, or None."""
    if not (MIN_SIZE <= width <= MAX_SIZE and MIN_SIZE <= height <= MAX_SIZE):
        return f"The canvas must be {MIN_SIZE} to {MAX_SIZE} pixels each way."
    boxes = drawn_boxes(project) if boxes is None else boxes
    lost = clipped_frames(project, width, height, grounded, boxes)
    if lost:
        w, h = smallest_size(project, grounded, boxes)
        return MSG_CLIPS.format(n=len(lost), total=len(project.frames), w=max(w, width), h=max(h, height))
    return None


def resize_project(project: Project, width: int, height: int, grounded: bool) -> None:
    """Give every frame and layer the new canvas. Refused (ValueError) if it would cut off drawn pixels."""
    why = problem(project, width, height, grounded)
    if why:
        raise ValueError(why)
    t = project.transparent
    for f in project.frames:
        f.image = place(f.image, width, height, t, grounded)
        if f.layers is not None:
            f.layers = tuple(place(im, width, height, t, grounded) for im in f.layers)
    project.width, project.height = width, height
    project.dirty = True
