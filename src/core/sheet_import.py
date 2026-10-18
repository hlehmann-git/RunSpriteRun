"""Import a filled-in blank sprite sheet (FR-1.5): find the boxes drawn in the box colour, cut out what is
inside each one and run the normal import checks on the pieces. Pure logic; shows nothing."""
from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image

from .colour import Colour
from .importer import ImportedFrame, ImportResult, Skipped, Adjustment, MSG_TRANSPARENCY, msg_too_many_colours, \
    msg_frame_limit
from .rules import MAX_FRAMES, MAX_SIZE, MIN_SIZE, default_label
from .systems import System

MSG_NO_BOXES = "No sprite boxes were found. Check the box colour matches the one used on the sheet."
MSG_UNEVEN = "The boxes on this sheet are not all the same size, so it cannot be imported."
def msg_sheet_colours(system: str, max_colours: int) -> str:
    return f"This sheet uses more colours than {system} allows (max {max_colours})."


MSG_ALL_EMPTY = "Every box on this sheet is empty, so there are no sprites to import."


def msg_box_size(w: int, h: int) -> str:
    return f"The boxes on this sheet are {w} x {h}. Sprite sizes must be {MIN_SIZE} to {MAX_SIZE} pixels."


@dataclass
class SheetGrid:
    width: int = 0
    height: int = 0
    boxes: list[tuple[int, int]] = field(default_factory=list)   # top-left of each box interior, row by row
    error: str | None = None


def _line_positions(flags: list[bool]) -> list[tuple[int, int]]:
    """Runs of consecutive True values as (first, last)."""
    runs, start = [], None
    for i, f in enumerate(flags + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            runs.append((start, i - 1))
            start = None
    return runs


def _long_run(values: bytes, need: int) -> bool:
    n = 0
    for v in values:
        n = n + 1 if v else 0
        if n >= need:
            return True
    return False


def find_grid(im: Image.Image, box: Colour) -> SheetGrid:
    """Boxes share single lines, so vertical lines and horizontal lines are found separately and the boxes are
    the spaces between neighbouring lines."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    r, g, b = rgb.split()
    mask = Image.merge("RGB", [x.point(lambda v, t=t: 255 if v == t else 0) for x, t in zip((r, g, b), box)])
    mr, mg, mb = mask.split()
    from PIL import ImageChops
    hit = ImageChops.multiply(ImageChops.multiply(mr, mg), mb).point(lambda v: 1 if v else 0)
    data = hit.tobytes()
    rows = [data[y * w:(y + 1) * w] for y in range(h)]
    cols = [data[x::w] for x in range(w)]
    vx = [_long_run(c, MIN_SIZE) for c in cols]
    hy = [_long_run(r_, MIN_SIZE) for r_ in rows]
    vruns, hruns = _line_positions(vx), _line_positions(hy)
    if len(vruns) < 2 or len(hruns) < 2:
        return SheetGrid(error=MSG_NO_BOXES)
    xs = [(a[1] + 1, b_[0] - 1) for a, b_ in zip(vruns, vruns[1:])]
    ys = [(a[1] + 1, b_[0] - 1) for a, b_ in zip(hruns, hruns[1:])]
    xs = [(a, b_) for a, b_ in xs if b_ >= a]
    ys = [(a, b_) for a, b_ in ys if b_ >= a]
    if not xs or not ys:
        return SheetGrid(error=MSG_NO_BOXES)
    widths = {b_ - a + 1 for a, b_ in xs}
    heights = {b_ - a + 1 for a, b_ in ys}
    if len(widths) != 1 or len(heights) != 1:
        return SheetGrid(error=MSG_UNEVEN)
    bw, bh = widths.pop(), heights.pop()
    if not (MIN_SIZE <= bw <= MAX_SIZE and MIN_SIZE <= bh <= MAX_SIZE):
        return SheetGrid(bw, bh, error=msg_box_size(bw, bh))
    return SheetGrid(bw, bh, [(x0, y0) for y0, _ in ys for x0, _ in xs])


def has_alpha(im: Image.Image) -> bool:
    if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info:
        return im.convert("RGBA").getchannel("A").getextrema()[0] < 255
    return False


def import_sheet(im: Image.Image, stem: str, grid: SheetGrid, fill: Colour, system: System) -> ImportResult:
    """Cut every box that holds something. A box that is all the fill colour is empty and is left out."""
    res = ImportResult()
    if grid.error:
        res.rejected = grid.error
        return res
    if has_alpha(im):
        res.rejected = MSG_TRANSPARENCY
        return res
    rgb = im.convert("RGB")
    w, h = grid.width, grid.height
    colours: set[Colour] = set()
    labels: set[str] = set()
    pieces = []
    for n, (x, y) in enumerate(grid.boxes, 1):
        piece = rgb.crop((x, y, x + w, y + h))
        found = piece.getcolors(w * h) or []
        if len(found) == 1 and found[0][1] == fill:
            continue
        pieces.append((n, piece))
    if not pieces:
        res.rejected = MSG_ALL_EMPTY
        return res
    if len(pieces) > MAX_FRAMES:
        res.rejected = msg_frame_limit(len(pieces))
        return res
    for _, piece in pieces:
        colours |= {c for _, c in system.snap_image(piece).getcolors(w * h)}
    colours.add(system.snap(fill))                                  # the fill colour becomes the transparent colour
    if len(colours) > system.max_colours:
        res.rejected = msg_sheet_colours(system.name, system.max_colours)
        return res
    for n, piece in pieces:
        name = f"{stem} box {n}"
        snapped = system.snap_image(piece)
        if snapped.tobytes() != piece.tobytes():
            details = []
            for _, orig in piece.getcolors(w * h):
                adj = system.snap(orig)
                if adj != orig:
                    details.append((orig, adj))
            res.adjustments.append(Adjustment(name, len(details), details))
        label = default_label(stem)
        res.frames.append(ImportedFrame(label, snapped))
    return res
