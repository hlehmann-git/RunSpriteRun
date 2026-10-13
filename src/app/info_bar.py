"""Information bar below the menu (FR-5.1): Project Name | System | Number of Frames | Number of Frame Groups,
on one line. Display only."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QWidget

from src.app.controller import Controller

BAR_H = 24
SEPARATOR = "   |   "


class InfoBar(QFrame):
    def __init__(self, parent: QWidget, controller: Controller) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setStyleSheet("InfoBar { background: #2a2c33; border-bottom: 1px solid #3a3d47; }"
                           "QLabel { color: #c9ccd6; font-size: 12px; }")
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.label.setGeometry(16, 0, 1248, BAR_H)
        controller.project_changed.connect(self.refresh)
        controller.frames_changed.connect(self.refresh)
        self.refresh()

    def text_for(self) -> str:
        p = self.controller.project
        if p is None:
            return ""
        return SEPARATOR.join((f"Project: {p.name}", f"System: {p.system.name}",
                               f"Frames: {len(p.frames)}", f"Frame Groups: {len(p.groups)}"))

    def refresh(self) -> None:
        self.label.setText(self.text_for())
