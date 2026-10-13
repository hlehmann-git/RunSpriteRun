"""Import validation (FR-1.1 to FR-1.4). Pure logic: reads files, returns a result, shows nothing."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .colour import Colour, snap_lut
from .rules import MAX_FRAMES, default_label
from .systems import System

ACCEPTED_SUFFIXES = (".png", ".bmp", ".gif")

MSG_TRANSPARENCY = ("Transparency (alpha) is not supported; use a solid colour for transparent "
                    "areas and set it as the transparent colour.")
MSG_GIF_ANIMATED = "Animated GIFs are not supported."


def msg_frame_limit(count: int) -> str:
    return (f"Maximum frames exceeded on import - you selected {count} files. "
            f"Please select {MAX_FRAMES} or fewer in total.")


def msg_too_many_colours(max_colours: int) -> str:
    return f"More colours in file than available for selected system (max {max_colours})."


def msg_size(name: str, w: int, h: int, pw: int, ph: int) -> str:
    return f"{name} is {w} x {h} but the project frame size is {pw} x {ph}."


def msg_unreadable(name: str) -> str:
    return f"{name} could not be read."


def msg_adjusted(n: int, name: str, system: str) -> str:
    return f"{n} colours in {name} were adjusted to the nearest colour valid for {system}."


def natural_key(path: Path) -> list:
    """Natural file-name order: frame2 before frame10, case-insensitive."""
    parts = re.split(r"(\d+)", path.name.lower())
    return [int(p) if p.isdigit() else p for p in parts]


@dataclass
class Skipped:
    file: str
    reason: str


@dataclass
class Adjustment:
    file: str
    count: int
    details: list[tuple[Colour, Colour]]    # (original, adjusted)


@dataclass
class ImportedFrame:
    label: str
    image: Image.Image


@dataclass
class ImportResult:
    frames: list[ImportedFrame] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)          # checks 3, 5 and unreadable files
    size_errors: list[str] = field(default_factory=list)          # check 2: blocks Create Project
    adjustments: list[Adjustment] = field(default_factory=list)   # check 4 warnings
    rejected: str | None = None                                   # check 1: whole import refused

    @property
    def transparent_default(self) -> Colour | None:
        """The first palette colour: the first pixel of the first frame (FR-3.13)."""
        if not self.frames:
            return None
        return self.frames[0].image.getpixel((0, 0))

    @property
    def can_create(self) -> bool:
        return self.rejected is None and not self.size_errors and bool(self.frames)


def read_size(path: Path) -> tuple[int, int] | None:
    """Image size without loading pixels, or None if unreadable (for 'Set from imported files')."""
    try:
        with Image.open(path) as im:
            return im.size
    except (OSError, UnidentifiedImageError):
        return None


def _has_transparency(im: Image.Image) -> bool:
    if im.format == "GIF":
        return "transparency" in im.info          # any transparent index counts (FR-1.2 check 3)
    if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info:
        alpha = im.convert("RGBA").getchannel("A")
        return alpha.getextrema()[0] < 255
    return False


def import_files(paths: list[Path], system: System, width: int, height: int) -> ImportResult:
    """Run the FR-1.2 checks in order over the files, in natural file-name order."""
    res = ImportResult()
    ordered = sorted((Path(p) for p in paths), key=natural_key)

    if len(ordered) > MAX_FRAMES:                                  # check 1
        res.rejected = msg_frame_limit(len(ordered))
        return res

    lut = snap_lut(system.bits) * 3
    colours: set[Colour] = set()
    labels: set[str] = set()

    for path in ordered:
        name = path.name
        try:
            with Image.open(path) as im:
                if path.suffix.lower() not in ACCEPTED_SUFFIXES or im.format not in ("PNG", "BMP", "GIF"):
                    res.skipped.append(Skipped(name, msg_unreadable(name)))
                    continue
                if im.format == "GIF" and getattr(im, "n_frames", 1) > 1:
                    res.skipped.append(Skipped(name, MSG_GIF_ANIMATED))
                    continue
                if im.size != (width, height):                     # check 2
                    res.size_errors.append(msg_size(name, im.size[0], im.size[1], width, height))
                    continue
                if _has_transparency(im):                          # check 3
                    res.skipped.append(Skipped(name, MSG_TRANSPARENCY))
                    continue
                rgb = im.convert("RGB")                            # EXIF/profiles ignored (FR-1.4)
        except (OSError, UnidentifiedImageError, ValueError, SyntaxError):
            res.skipped.append(Skipped(name, msg_unreadable(name)))
            continue

        snapped = rgb.point(lut)                                   # check 4
        if snapped.tobytes() != rgb.tobytes():
            before = dict.fromkeys(c for _, c in (rgb.getcolors(width * height) or []))
            details = []
            for orig in before:
                adj = (lut[orig[0]], lut[orig[1]], lut[orig[2]])
                if adj != orig:
                    details.append((orig, adj))
            res.adjustments.append(Adjustment(name, len(details), details))

        file_colours = {c for _, c in (snapped.getcolors(width * height) or [])}
        if len(colours | file_colours) > system.max_colours:       # check 5
            res.skipped.append(Skipped(name, msg_too_many_colours(system.max_colours)))
            continue

        colours |= file_colours
        label = default_label(path.stem, labels)
        labels.add(label)
        res.frames.append(ImportedFrame(label, snapped))

    return res
