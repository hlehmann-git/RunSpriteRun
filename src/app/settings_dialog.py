"""Settings window (File > Settings), available only while a project is open. It holds the options of the open
project: today its Frames per second (3, 6, 12 or 24). OK applies it to the project (one Undo step); Cancel changes
nothing. The sprite sheet options belong to the Export dialog and the pixel grid is always on."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.app.theme import short_popup
from src.core.rules import FPS_CHOICES


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self.setMinimumSize(360, 200)
        self.controller = getattr(parent, "controller", None)
        project = self.controller.project if self.controller else None
        self.fps = QComboBox()
        for f in FPS_CHOICES:
            self.fps.addItem(str(f), f)
        if project is not None:
            self.fps.setCurrentIndex(self.fps.findData(project.fps))
        short_popup(self.fps)
        hint = QLabel("The playback speed of this project, for every frame group and RunSpriteRun.")
        hint.setWordWrap(True)
        row_fps = QHBoxLayout()
        row_fps.addWidget(QLabel("Frames per second"))
        row_fps.addWidget(self.fps)
        row_fps.addStretch()
        ok = QPushButton("OK")
        ok.setDefault(True)
        ok.clicked.connect(self._ok)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(ok)
        row.addWidget(cancel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.addLayout(row_fps)
        layout.addWidget(hint)
        layout.addStretch()
        layout.addLayout(row)

    def _ok(self) -> None:
        if self.controller is not None:
            self.controller.set_fps(self.fps.currentData())
        self.accept()
