"""A small square button with a filled triangle (left or right), used to step through frames."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPolygonF
from PySide6.QtWidgets import QPushButton, QWidget

from src.app.theme import TOGGLE_BUTTON_STYLE


class ArrowButton(QPushButton):
    SIZE = 22

    def __init__(self, direction: str, parent: QWidget, tip: str) -> None:
        super().__init__("", parent)
        assert direction in ("left", "right")
        self.direction = direction
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setStyleSheet(TOGGLE_BUTTON_STYLE)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip(tip)
        self.setAccessibleName(tip)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(230, 232, 238) if self.isEnabled() else QColor(120, 120, 128))
        cx, cy, s = self.width() / 2, self.height() / 2, 1.0
        if self.direction == "left":
            pts = [QPointF(cx - 3.5 * s, cy), QPointF(cx + 3.5 * s, cy - 5 * s), QPointF(cx + 3.5 * s, cy + 5 * s)]
        else:
            pts = [QPointF(cx + 3.5 * s, cy), QPointF(cx - 3.5 * s, cy - 5 * s), QPointF(cx - 3.5 * s, cy + 5 * s)]
        p.drawPolygon(QPolygonF(pts))
