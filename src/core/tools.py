"""Drawing tools (V2.0): pure functions that turn mouse positions into sets of pixels. No UI code, no images."""
from __future__ import annotations

TOOLS = ("pencil", "eraser", "bucket", "select", "move", "plus", "line", "square", "circle")
MAX_THICKNESS = 16


def line_points(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Bresenham line, both ends included."""
    pts = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return pts
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def pixel_perfect(path: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Drop the middle pixel of an L-shaped corner so a thin stroke has no doubled pixels."""
    if len(path) < 3:
        return list(path)
    out = [path[0]]
    for i in range(1, len(path) - 1):
        a, b, c = out[-1], path[i], path[i + 1]
        corner = abs(a[0] - c[0]) == 1 and abs(a[1] - c[1]) == 1 and (b[0] == a[0] or b[1] == a[1]) and b != a and b != c
        if not corner:
            out.append(b)
    out.append(path[-1])
    return out


def brush(x: int, y: int, thickness: int, shape: str = "Square") -> list[tuple[int, int]]:
    """The pixels of one brush dab centred (as near as a whole pixel allows) on x, y."""
    t = max(1, min(thickness, MAX_THICKNESS))
    x0, y0 = x - (t - 1) // 2, y - (t - 1) // 2
    if shape != "Round" or t < 3:
        return [(x0 + i, y0 + j) for j in range(t) for i in range(t)]
    c = (t - 1) / 2
    r2 = (t / 2) ** 2
    return [(x0 + i, y0 + j) for j in range(t) for i in range(t) if (i - c) ** 2 + (j - c) ** 2 <= r2]


def stroke(path: list[tuple[int, int]], thickness: int, shape: str, perfect: bool) -> set[tuple[int, int]]:
    """A pencil or eraser stroke through the mouse positions in `path`."""
    if not path:
        return set()
    joined = [path[0]]
    for a, b in zip(path, path[1:]):
        joined.extend(line_points(a[0], a[1], b[0], b[1])[1:])
    if perfect and thickness == 1:
        joined = pixel_perfect(joined)
    pts: set[tuple[int, int]] = set()
    for x, y in joined:
        pts.update(brush(x, y, thickness, shape))
    return pts


def lock_axis(start: tuple[int, int], end: tuple[int, int]) -> tuple[int, int]:
    """Shift with the pencil: horizontal or vertical, whichever way the mouse has gone further."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    return (end[0], start[1]) if abs(dx) >= abs(dy) else (start[0], end[1])


def lock_angle(start: tuple[int, int], end: tuple[int, int]) -> tuple[int, int]:
    """Shift with the line: horizontal, vertical or 45 degrees (nearest of the eight directions)."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    ax, ay = abs(dx), abs(dy)
    if ax >= 2 * ay:
        return (end[0], start[1])
    if ay >= 2 * ax:
        return (start[0], end[1])
    m = max(ax, ay)
    return (start[0] + (m if dx >= 0 else -m), start[1] + (m if dy >= 0 else -m))


def line_shape(start, end, thickness: int, shape: str, lock: bool) -> set[tuple[int, int]]:
    if lock:
        end = lock_angle(start, end)
    pts: set[tuple[int, int]] = set()
    for x, y in line_points(start[0], start[1], end[0], end[1]):
        pts.update(brush(x, y, thickness, shape))
    return pts


def _box(start, end, centre: bool, lock: bool) -> tuple[int, int, int, int]:
    """Inclusive corners (x0, y0, x1, y1) of the box dragged out from `start` to `end`."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    if lock:                                            # Shift: a square / a true circle
        m = max(abs(dx), abs(dy))
        dx, dy = (m if dx >= 0 else -m), (m if dy >= 0 else -m)
    if centre:
        return start[0] - abs(dx), start[1] - abs(dy), start[0] + abs(dx), start[1] + abs(dy)
    return min(start[0], start[0] + dx), min(start[1], start[1] + dy), max(start[0], start[0] + dx), max(start[1], start[1] + dy)


def _ellipse(x0: int, y0: int, x1: int, y1: int, shrink: int = 0) -> set[tuple[int, int]]:
    a, b = (x1 - x0 + 1) / 2 - shrink, (y1 - y0 + 1) / 2 - shrink
    if a <= 0 or b <= 0:
        return set()
    cx, cy = (x0 + x1 + 1) / 2, (y0 + y1 + 1) / 2
    return {(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
            if ((x + 0.5 - cx) / a) ** 2 + ((y + 0.5 - cy) / b) ** 2 <= 1.0}


def rect_parts(start, end, thickness: int, centre: bool, lock: bool):
    """(outline, whole) pixel sets of the box dragged out from start to end. The outline grows inwards."""
    x0, y0, x1, y1 = _box(start, end, centre, lock)
    full = {(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}
    t = max(1, min(thickness, MAX_THICKNESS))
    return full - {(x, y) for y in range(y0 + t, y1 - t + 1) for x in range(x0 + t, x1 - t + 1)}, full


def rect_shape(start, end, thickness: int, filled: bool, centre: bool, lock: bool) -> set[tuple[int, int]]:
    outline, full = rect_parts(start, end, thickness, centre, lock)
    return full if filled else outline


def ellipse_outline(x0: int, y0: int, x1: int, y1: int) -> set[tuple[int, int]]:
    """A one pixel wide ellipse inside the box (x0, y0)-(x1, y1), both corners included: one pixel per step, no
    doubled corner pixels (Alois Zingl's rectangle ellipse)."""
    a, b = abs(x1 - x0), abs(y1 - y0)
    b1 = b & 1
    dx, dy = 4 * (1 - a) * b * b, 4 * (b1 + 1) * a * a
    err = dx + dy + b1 * a * a
    if x0 > x1:
        x0, x1 = x1, x1 + a
    if y0 > y1:
        y0 = y1
    y0 += (b + 1) // 2
    y1 = y0 - b1
    a8, b8 = 8 * a * a, 8 * b * b
    pts: set[tuple[int, int]] = set()
    while True:
        pts.update(((x1, y0), (x0, y0), (x0, y1), (x1, y1)))
        e2 = 2 * err
        if e2 <= dy:
            y0 += 1
            y1 -= 1
            dy += a8
            err += dy
        if e2 >= dx or 2 * err > dy:
            x0 += 1
            x1 -= 1
            dx += b8
            err += dx
        if x0 > x1:
            break
    while y0 - y1 < b:                                    # the flat tips of a thin ellipse
        pts.update(((x0 - 1, y0), (x1 + 1, y0)))
        y0 += 1
        pts.update(((x0 - 1, y1), (x1 + 1, y1)))
        y1 -= 1
    return pts


def _scanline_fill(outline: set[tuple[int, int]]) -> set[tuple[int, int]]:
    rows: dict[int, list[int]] = {}
    for x, y in outline:
        rows.setdefault(y, []).append(x)
    return {(x, y) for y, xs in rows.items() for x in range(min(xs), max(xs) + 1)}


def circle_parts(start, end, thickness: int, centre: bool, lock: bool):
    """(outline, whole) pixel sets of the ellipse dragged out from start to end. At thickness 1 the outline is
    pixel perfect; thicker outlines grow inwards."""
    x0, y0, x1, y1 = _box(start, end, centre, lock)
    t = max(1, min(thickness, MAX_THICKNESS))
    if t == 1:
        outline = ellipse_outline(x0, y0, x1, y1)
        return outline, _scanline_fill(outline)
    outer = _ellipse(x0, y0, x1, y1)
    return outer - _ellipse(x0, y0, x1, y1, t), outer


def circle_shape(start, end, thickness: int, filled: bool, centre: bool, lock: bool) -> set[tuple[int, int]]:
    outline, whole = circle_parts(start, end, thickness, centre, lock)
    return whole if filled else outline


def flood(get, width: int, height: int, x: int, y: int, contiguous: bool) -> set[tuple[int, int]]:
    """The pixels a bucket fill at x, y covers; `get(x, y)` is the colour of a pixel."""
    if not (0 <= x < width and 0 <= y < height):
        return set()
    want = get(x, y)
    if not contiguous:
        return {(i, j) for j in range(height) for i in range(width) if get(i, j) == want}
    seen = {(x, y)}
    todo = [(x, y)]
    while todo:
        cx, cy = todo.pop()
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen and get(nx, ny) == want:
                seen.add((nx, ny))
                todo.append((nx, ny))
    return seen
