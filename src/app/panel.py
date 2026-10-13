"""Common look of the main window panels (dark theme)."""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QWidget

PANEL_STYLE = "Panel { background: #2a2c33; border: 1px solid #3a3d47; border-radius: 8px; }"


class Panel(QFrame):
    def __init__(self, title: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)
        self.title = QLabel(title, self)
        font = QFont(self.title.font())
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() + 1)
        self.title.setFont(font)
        self.title.move(16, 10)
        self.title.adjustSize()
