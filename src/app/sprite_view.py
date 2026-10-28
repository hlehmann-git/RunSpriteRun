"""A fixed-size sprite view (256 x 256 logical pixels), drawn 1:1 in physical pixels (section 5.1)."""
from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QObject, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

import math

from src.app.render import fit_scale, render_sprite, render_sprite_at, render_window, to_qimage
from src.core.colour import Colour

VIEW_SIZE = 256
MAX_SCALE = 64


class SpriteView(QWidget):
    pixel_clicked = Signal(int, int)       # sprite pixel (x, y) under a left click
    pixel_right_clicked = Signal(int, int)
    drag_started = Signal(int, int, bool)  # Edit mode: pixel under the mouse (it can be outside the sprite), Shift held
    drag_moved = Signal(int, int, bool)
    drag_ended = Signal(int, int, bool)
    zoom_changed = Signal()
    placed = Signal(float, float)          # a mirror guide line is being placed: the clicked point, in sprite pixels

    def __init__(self, parent: QWidget, grid: bool, size: int = VIEW_SIZE) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.grid = grid
        self._image: Image.Image | None = None
        self._transparent: Colour = (0, 0, 0)
        self.zoom: int | None = None          # None: the largest whole-number scale that fits
        self.draggable = False                # Edit mode: report the mouse as it draws
        self._dragging = False
        self.navigable = False                # Edit mode: whole-number zoom and panning of a large sprite
        self.scale: int | None = None         # None: the largest scale that fits
        self.centre: tuple[float, float] | None = None    # the sprite point in the middle of the view (None: the sprite's middle)
        self._panning = None                  # (last x, last y) while the picture is being dragged
        self._space = False
        self.tool_cursor = None               # Edit mode: the pointer of the chosen tool (None: the arrow)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(False)
        self.placing = False                  # Edit mode: the next left click places a mirror guide line
        self.selection = None                 # Edit mode: the selected rectangle (x0, y0, x1, y1) in sprite pixels
        self.guides: dict[str, int | None] = {"v": None, "h": None}   # guide lines, in half pixels

    def _geometry(self):
        """dpr, scale, left, top of the sprite in physical view pixels, sprite width and height."""
        dpr = self.devicePixelRatioF()
        pw, ph = self.physical_size()
        w, h = self._image.size
        fit = fit_scale(w, h, pw, ph)
        if self.navigable:
            sc = max(fit, min(MAX_SCALE, self.scale or fit))
            cx, cy = self.centre if (self.centre is not None and sc > fit) else (w / 2, h / 2)
            return dpr, sc, math.floor(pw / 2 - cx * sc), math.floor(ph / 2 - cy * sc), w, h
        s = fit if self.zoom is None else max(1, min(self.zoom, fit))
        return dpr, s, (pw - w * s) // 2, (ph - h * s) // 2, w, h

    # ---- zoom and pan (Edit mode) ------------------------------------------------------------------------
    def current_scale(self) -> int:
        return self._geometry()[1] if self._image is not None else 1

    def fit(self) -> int:
        pw, ph = self.physical_size()
        return fit_scale(*self._image.size, pw, ph) if self._image is not None else 1

    def set_scale(self, scale: int, anchor=None) -> None:
        """Zoom to a whole-number scale (never below what fits the view), keeping the sprite point under `anchor`
        (a point of the view, logical pixels) where it is; no anchor: the middle of the view."""
        if self._image is None or not self.navigable:
            return
        dpr, old, left, top, w, h = self._geometry()
        pw, ph = self.physical_size()
        new = max(self.fit(), min(MAX_SCALE, scale))
        ax, ay = (anchor.x() * dpr, anchor.y() * dpr) if anchor is not None else (pw / 2, ph / 2)
        fx, fy = (ax - left) / old, (ay - top) / old                 # the sprite point under the anchor
        self.scale = new
        self.centre = (fx - (ax - pw / 2) / new, fy - (ay - ph / 2) / new)
        self._clamp()
        self.update()
        self.zoom_changed.emit()

    def _clamp(self) -> None:
        if self.centre is None or self._image is None:
            return
        w, h = self._image.size
        self.centre = (max(0.0, min(float(w), self.centre[0])), max(0.0, min(float(h), self.centre[1])))

    def reset_zoom(self) -> None:
        self.scale, self.centre, self._panning, self._space = None, None, None, False
        self.update()
        self.zoom_changed.emit()

    def wheelEvent(self, event) -> None:
        if not self.navigable or self._image is None:
            return event.ignore()
        step = 1 if event.angleDelta().y() > 0 else -1 if event.angleDelta().y() < 0 else 0
        if step:
            self.set_scale(self.current_scale() + step, event.position())
        event.accept()

    def enterEvent(self, event) -> None:
        if self.navigable:
            self.setFocus()                    # so that Space can be held for panning
        super().enterEvent(event)

    def keyPressEvent(self, event) -> None:
        if self.navigable and event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space = True
            self.setCursor(Qt.OpenHandCursor)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space = False
            if self._panning is None:
                self.setCursor(self._idle_cursor())
        else:
            super().keyReleaseEvent(event)

    def _start_pan(self, pos) -> None:
        self._panning = (pos.x(), pos.y())
        self.setCursor(Qt.ClosedHandCursor)

    def _pan_to(self, pos) -> None:
        dpr, s, *_ = self._geometry()
        if self.scale is None or s <= self.fit():
            return                                       # everything fits: nothing to pan
        lx, ly = self._panning
        cx, cy = self.centre if self.centre is not None else (self._image.size[0] / 2, self._image.size[1] / 2)
        self.centre = (cx - (pos.x() - lx) * dpr / s, cy - (pos.y() - ly) * dpr / s)
        self._clamp()
        self._panning = (pos.x(), pos.y())
        self.update()

    def set_selection(self, rect) -> None:
        if rect != self.selection:
            self.selection = rect
            self.update()

    def set_guides(self, guides: dict) -> None:
        self.guides = dict(guides)
        self.update()

    def _idle_cursor(self):
        if self._space:
            return Qt.OpenHandCursor
        if self.placing:
            return Qt.CrossCursor
        return self.tool_cursor if self.tool_cursor is not None else Qt.ArrowCursor

    def set_tool_cursor(self, cursor) -> None:
        self.tool_cursor = cursor
        if self._panning is None:
            self.setCursor(self._idle_cursor())

    def set_placing(self, on: bool) -> None:
        self.placing = on
        if self._panning is None:
            self.setCursor(self._idle_cursor())

    def set_sprite(self, image: Image.Image | None, transparent: Colour = (0, 0, 0)) -> None:
        self._image = image
        self._transparent = transparent
        self.update()

    def physical_size(self) -> tuple[int, int]:
        dpr = self.devicePixelRatioF()
        return round(self.width() * dpr), round(self.height() * dpr)

    def max_zoom(self, w: int, h: int) -> int:
        """The largest whole-number scale for a w x h sprite, in physical pixels (FR-3.3)."""
        pw, ph = self.physical_size()
        return fit_scale(w, h, pw, ph)

    def set_zoom(self, zoom: int | None) -> None:
        self.zoom = zoom
        self.update()

    def pixel_at(self, pos) -> tuple[int, int] | None:
        """The sprite pixel under a point of the view (logical pixels), or None outside the sprite."""
        hit = self.pixel_at_any(pos)
        if hit is None:
            return None
        w, h = self._image.size
        return hit if 0 <= hit[0] < w and 0 <= hit[1] < h else None

    def pixel_at_any(self, pos) -> tuple[int, int] | None:
        """Like pixel_at, but also gives positions outside the sprite (they can be negative or too big)."""
        if self._image is None:
            return None
        dpr, s, ox, oy, w, h = self._geometry()
        return (int(pos.x() * dpr) - ox) // s, (int(pos.y() * dpr) - oy) // s

    def mousePressEvent(self, event) -> None:
        if self.navigable and (event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self._space)):
            self._start_pan(event.position())
            return
        if event.button() == Qt.RightButton:
            hit = self.pixel_at(event.position().toPoint())
            if hit is not None:
                self.pixel_right_clicked.emit(*hit)
        if event.button() == Qt.LeftButton and self.placing and self._image is not None:
            dpr, s, ox, oy, w, h = self._geometry()
            pos = event.position()
            self.placed.emit((pos.x() * dpr - ox) / s, (pos.y() * dpr - oy) / s)
            return
        if event.button() == Qt.LeftButton:
            hit = self.pixel_at(event.position().toPoint())
            if hit is not None:
                self.pixel_clicked.emit(*hit)
                if self.draggable:
                    self._dragging = True
                    self.drag_started.emit(*hit, bool(event.modifiers() & Qt.ShiftModifier))

    def mouseMoveEvent(self, event) -> None:
        if self._panning is not None:
            self._pan_to(event.position())
            return
        if self._dragging:
            hit = self.pixel_at_any(event.position().toPoint())
            if hit is not None:
                self.drag_moved.emit(*hit, bool(event.modifiers() & Qt.ShiftModifier))

    def mouseReleaseEvent(self, event) -> None:
        if self._panning is not None and event.button() in (Qt.MiddleButton, Qt.LeftButton):
            self._panning = None
            self.setCursor(self._idle_cursor())
            return
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            hit = self.pixel_at_any(event.position().toPoint())
            if hit is not None:
                self.drag_ended.emit(*hit, bool(event.modifiers() & Qt.ShiftModifier))

    def paintEvent(self, event) -> None:
        dpr = self.devicePixelRatioF()
        pw, ph = round(self.width() * dpr), round(self.height() * dpr)
        if self._image is None:
            frame = Image.new("RGB", (pw, ph), (0, 0, 0))
        else:
            if self.navigable:
                _d, sc, left, top, _w, _h = self._geometry()
                frame = render_window(self._image, self._transparent, pw, ph, sc, left, top, self.grid)
            elif self.zoom is None:
                frame = render_sprite(self._image, self._transparent, pw, ph, self.grid)
            else:
                frame = render_sprite_at(self._image, self._transparent, pw, ph, self.zoom)
        painter = QPainter(self)
        painter.drawImage(0, 0, to_qimage(frame, dpr))
        if self._image is not None and self.selection is not None:
            _dpr, s, ox, oy, w, h = self._geometry()
            x0, y0, x1, y1 = self.selection
            r = QRectF((ox + x0 * s) / dpr, (oy + y0 * s) / dpr, (x1 - x0) * s / dpr, (y1 - y0) * s / dpr)
            r.adjust(0.5, 0.5, -0.5, -0.5)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#000000"), 1))                 # a dotted outline that shows on light and dark
            painter.drawRect(r)
            white = QPen(QColor("#ffffff"), 1, Qt.CustomDashLine)
            white.setDashPattern([3, 3])
            painter.setPen(white)
            painter.drawRect(r)
        if self._image is not None and any(v is not None for v in self.guides.values()):
            _dpr, s, ox, oy, w, h = self._geometry()
            painter.setPen(QPen(QColor("#ffe600"), 2))
            if self.guides.get("v") is not None:
                x = (ox + self.guides["v"] * s / 2) / dpr
                painter.drawLine(round(x), 0, round(x), self.height())
            if self.guides.get("h") is not None:
                y = (oy + self.guides["h"] * s / 2) / dpr
                painter.drawLine(0, round(y), self.width(), round(y))


def offer_to_picker(view: SpriteView, controller) -> None:
    """With the colour picker (eyedropper) on, a click on a pixel of this view takes its colour, as in the Frame
    view: left click the primary colour, right click the secondary. Used by the Frame Group Preview and the
    RunSpriteRun window. A click on the see-through background gives the transparent colour."""
    def pick(x: int, y: int, right: bool) -> None:
        img = view._image
        if not controller.eyedropper_armed or img is None:
            return
        colour = tuple(img.convert("RGB").getpixel((x, y)) if img.mode != "RGB" else img.getpixel((x, y)))
        (controller.frame_pixel_right_clicked if right else controller.frame_pixel_clicked).emit(colour)

    view.pixel_clicked.connect(lambda x, y: pick(x, y, False))
    view.pixel_right_clicked.connect(lambda x, y: pick(x, y, True))
