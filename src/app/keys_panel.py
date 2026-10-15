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

HELD_BG, HELD_FG = QColor("#9fd3ff"), QColor("#14141a")      # a held key is filled with its group's colour (this if none)
KEY_BG, KEY_FG, KEY_EDGE = QColor("#1e1f24"), QColor("#e6e8ee"), QColor("#78808c")
PAD_W, PAD_H = 156, 142
# (key, centre x, centre y, size, round?) inside the pad: W A S D as a cross, the four "+" diagonals between them, 1 to 6 as round buttons
_CX, _CY, _STEP = 78, 52, 31
KEY_LAYOUT = (
    [("W", _CX, _CY - _STEP, 25, False), ("A", _CX - _STEP, _CY, 25, False),
     ("S", _CX, _CY + _STEP, 25, False), ("D", _CX + _STEP, _CY, 25, False),
     ("W+A", _CX - _STEP, _CY - _STEP, 20, False), ("W+D", _CX + _STEP, _CY - _STEP, 20, False),
     ("S+A", _CX - _STEP, _CY + _STEP, 20, False), ("S+D", _CX + _STEP, _CY + _STEP, 20, False)]
    + [(str(n), 21 + 23 * (n - 1), 118, 20, True) for n in range(1, 7)]      # 1 to 6 in one row under the cross
)


class KeyPad(QWidget):
    """Shows only which keys are held. It never shows which keys have a group (colour fills a key only while it is held)."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(PAD_W, PAD_H)
        self.setAccessibleName("Keys held")
        self.held: set[str] = set()
        self.colour_of = lambda key: None               # set by the timeline: a key's group colour, or None

    def set_held(self, keys) -> None:
        self.held = set(keys)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#626674"), 1.5))
        p.setBrush(QColor("#3b3e48"))
        p.drawRoundedRect(QRectF(1, 1, PAD_W - 2, PAD_H - 2), 24, 24)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#2c2e38"))
        p.drawRect(_CX - 12, _CY - 12, 25, 25)           # the middle of the cross
        font = QFont(self.font())
        font.setBold(True)
        for key, cx, cy, size, round_ in KEY_LAYOUT:
            on = key in self.held
            rect = QRectF(cx - size / 2, cy - size / 2, size, size)
            fill = (self.colour_of(key) or HELD_BG) if on else KEY_BG
            p.setPen(QPen(fill if on else KEY_EDGE, 1))
            p.setBrush(fill)
            if round_:
                p.drawEllipse(rect)
            else:
                p.drawRoundedRect(rect, 6, 6)
            font.setPixelSize(18 if "+" in key else 14 if not round_ else 12)
            p.setFont(font)
            p.setPen(HELD_FG if on else KEY_FG)
            p.drawText(rect, Qt.AlignCenter, "+" if "+" in key else key)


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
