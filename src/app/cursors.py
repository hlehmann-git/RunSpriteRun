"""Mouse pointers for the drawing tools in the Frame view (V2.0 Edit mode), drawn in code like the tool icons.
Each has a hot spot on the pixel it will change: the pencil's tip, the eraser's middle, the crosshair's centre."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

SIZE = 32
_cache: dict[str, QCursor] = {}


def _canvas() -> tuple[QPixmap, QPainter]:
    pm = QPixmap(SIZE, SIZE)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    return pm, p


def _poly(p: QPainter, pts, fill: str, line: str = "#16181d") -> None:
    p.setPen(QPen(QColor(line), 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QColor(fill))
    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))


def _pencil() -> QCursor:
    pm, p = _canvas()
    # a pencil pointing down and to the left: tip at (2, 29)
    _poly(p, [(2, 29), (7, 22), (10, 25)], "#e9c79a")            # sharpened wood
    _poly(p, [(7, 22), (10, 25), (24, 14), (21, 11)], "#f2c21b")   # body
    _poly(p, [(21, 11), (24, 14), (27, 12), (24, 9)], "#e8838f")   # eraser
    p.setPen(QPen(QColor("#16181d"), 1.2))
    p.drawPoint(QPointF(2.5, 28.5))
    p.end()
    return QCursor(pm, 2, 29)


def _eraser() -> QCursor:
    pm, p = _canvas()
    _poly(p, [(6, 6), (26, 6), (26, 26), (6, 26)], "#00000000", "#ffffff")
    _poly(p, [(8, 8), (24, 8), (24, 24), (8, 24)], "#6ee8838f", "#16181d")
    p.end()
    return QCursor(pm, 16, 16)


def _bucket() -> QCursor:
    pm, p = _canvas()
    _poly(p, [(8, 6), (24, 12), (19, 26), (3, 20)], "#9aa0ae")        # a tipped bucket
    _poly(p, [(3, 20), (6, 21), (4, 28), (1, 27)], "#3780cd")         # the paint, with the hot spot at its drop
    p.end()
    return QCursor(pm, 3, 28)


def _cross() -> QCursor:
    pm, p = _canvas()
    c = SIZE / 2
    for width, colour in ((3.4, "#16181d"), (1.4, "#ffffff")):
        p.setPen(QPen(QColor(colour), width, Qt.SolidLine, Qt.FlatCap))
        p.drawLine(QPointF(c, 4), QPointF(c, c - 4))
        p.drawLine(QPointF(c, c + 4), QPointF(c, SIZE - 4))
        p.drawLine(QPointF(4, c), QPointF(c - 4, c))
        p.drawLine(QPointF(c + 4, c), QPointF(SIZE - 4, c))
    p.end()
    return QCursor(pm, SIZE // 2, SIZE // 2)


def cursor_for(tool: str) -> QCursor | None:
    """The pointer for a tool, or None for the ordinary arrow."""
    if tool == "move":
        return QCursor(Qt.SizeAllCursor)
    make = {"pencil": _pencil, "eraser": _eraser, "bucket": _bucket,
            "line": _cross, "square": _cross, "circle": _cross}.get(tool)
    if make is None:
        return None
    if tool not in _cache:
        _cache[tool] = make()
    return _cache[tool]
