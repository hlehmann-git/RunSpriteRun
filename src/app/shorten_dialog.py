"""Edit > Shorten Frame Names: the text every frame name starts with is swapped for a shorter text of your own.
The window shows the shared text and an example of before and after. It cannot be undone."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout, QWidget)

from src.core.edit import EditError, shared_prefix, shortened_names
from src.core.project import Project
from src.core.rules import NAME_MAX

WARNING = "This cannot be undone. Do not save the project if you want to keep the original names."


class ShortenDialog(QDialog):
    def __init__(self, parent: QWidget, project: Project) -> None:
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Shorten Frame Names")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        prefix = shared_prefix(project)
        intro = QLabel("Text that every frame name starts with is swapped for the text you type. "
                       "The numbers (_001, _002 ...) stay.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.shared = QLabel(f"Shared text: {prefix}" if prefix else "The frame names have no text in common at the start.")
        self.shared.setWordWrap(True)
        lay.addWidget(self.shared)
        self.name = QLineEdit()
        self.name.setMaxLength(NAME_MAX)
        self.name.setPlaceholderText("New text, e.g. Rick")
        lay.addWidget(self.name)
        self.example = QLabel("")
        self.example.setWordWrap(True)
        self.example.setStyleSheet("color: #9aa0ae;")
        lay.addWidget(self.example)
        warn = QLabel(WARNING)
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #d6a046;")
        lay.addWidget(warn)
        self.box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.box.accepted.connect(self.accept)
        self.box.rejected.connect(self.reject)
        lay.addWidget(self.box)
        self.name.textChanged.connect(self._changed)
        self._changed("")

    def replacement(self) -> str:
        return self.name.text()

    def _changed(self, text: str) -> None:
        ok = False
        try:
            names = shortened_names(self.project, text)
            first = self.project.frames[0].label
            self.example.setText(f"{first}  becomes  {names[0]}_{first.rsplit('_', 1)[-1]}")
            ok = True
        except EditError as e:
            self.example.setText(str(e) if text else "")
        self.box.button(QDialogButtonBox.Ok).setEnabled(ok)
