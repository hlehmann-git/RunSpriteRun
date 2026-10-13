"""Key pad (FR-3.12): a small game-controller drawing with W, A, S, D as a cross and 1 to 6 as round buttons.
Display-only: a key is highlighted (light blue, dark red text) while it is held in RunSpriteRun. It sits in the
Timeline and frames panel. The Keys panel itself is an empty slot, kept for version 2."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from src.app.controller import Controller
from src.app.panel import Panel

HELD_BG, HELD_FG = QColor("#9fd3ff"), QColor("#8b0000")
KEY_BG, KEY_FG, KEY_EDGE = QColor("#1e1f24"), QColor("#e6e8ee"), QColor("#4a4e5a")
# (key, x, y, size, round?) inside the 100 x 60 pad
KEY_LAYOUT = (
    [("W", 16, 8, 14, False), ("A", 2, 22, 14, False), ("D", 30, 22, 14, False), ("S", 16, 36, 14, False)]
    + [(str(n), 52 + 16 * ((n - 1) % 3), 15 + 16 * ((n - 1) // 3), 14, True) for n in range(1, 7)]
)


PAD_W, PAD_H = 100, 60


class KeyPad(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(PAD_W, PAD_H)
        self.setAccessibleName("Keys held")
        self.held: set[str] = set()

    def set_held(self, keys) -> None:
        self.held = set(keys)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#5a5e6b"), 1))
        p.setBrush(QColor("#3b3e48"))
        p.drawRoundedRect(QRectF(0.5, 0.5, PAD_W - 1, PAD_H - 1), 16, 16)
        p.setPen(Qt.NoPen)
        p.setBrush(KEY_BG)
        p.drawRect(16, 22, 14, 14)                       # the middle of the cross
        font = QFont(self.font())
        font.setPixelSize(8)
        font.setBold(True)
        p.setFont(font)
        for key, x, y, size, round_ in KEY_LAYOUT:
            on = key in self.held
            p.setPen(QPen(KEY_EDGE, 1))
            p.setBrush(HELD_BG if on else KEY_BG)
            rect = QRectF(x + 0.5, y + 0.5, size - 1, size - 1)
            if round_:
                p.drawEllipse(rect)
            else:
                p.drawRoundedRect(rect, 2, 2)
            p.setPen(HELD_FG if on else KEY_FG)
            p.drawText(QRectF(x, y, size, size), Qt.AlignCenter, key)


class KeysPanel(Panel):
    """The slot (688 x 208, running to the right edge of the window) that keeps the Keys panel's place. Version 1.b: it shows a picture of the future
    Edit panel. The picture is cosmetic only: nothing in it can be clicked and it does nothing."""

    def __init__(self, parent: QWidget, controller: Controller) -> None:
        super().__init__("", parent)
        self.title.hide()
        self.picture = QLabel(self)
        self.picture.setPixmap(QPixmap(str(Path(__file__).parent / "assets" / "edit_panel.png")))
        self.picture.setGeometry(1, 1, 686, 206)
        self.picture.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.picture.setAccessibleName("Edit panel (picture only, not active yet)")
