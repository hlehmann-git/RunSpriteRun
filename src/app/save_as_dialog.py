"""File > Save As (FR-4.4): the new project's name and the parent folder. The project folder is made inside the
parent folder and the .rsr is saved inside it."""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from src.core.rules import PROJECT_NAME_MAX, valid_project_name


class SaveAsDialog(QDialog):
    def __init__(self, parent: QWidget, name: str, folder: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save As")
        self.setModal(True)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel("New project name"), 0, 0)
        self.name = QLineEdit(name)
        self.name.setMaxLength(60)                     # longer entries are flagged, not silently cut
        grid.addWidget(self.name, 0, 1, 1, 2)
        grid.addWidget(QLabel("Parent folder"), 1, 0)
        self.folder = QLineEdit(folder)
        grid.addWidget(self.folder, 1, 1)
        self.browse = QPushButton("Browse...")
        grid.addWidget(self.browse, 1, 2)
        self.name_hint = QLabel("")
        self.hint = QLabel("A folder with this name is created in the parent folder and holds the .rsr file.")
        self.hint.setStyleSheet("color: #9aa0ae;")
        row = QHBoxLayout()
        row.addStretch(1)
        self.ok = QPushButton("OK")
        self.ok.setDefault(True)
        cancel = QPushButton("Cancel")
        row.addWidget(self.ok)
        row.addWidget(cancel)
        root = QVBoxLayout(self)
        root.addLayout(grid)
        root.addWidget(self.name_hint)
        root.addWidget(self.hint)
        root.addLayout(row)
        self.ok.clicked.connect(self.accept)
        self.name.textChanged.connect(self._check_name)
        self._check_name()
        cancel.clicked.connect(self.reject)
        self.browse.clicked.connect(self._browse)
        self.setMinimumWidth(520)
        self.setFixedHeight(self.sizeHint().height())

    def _check_name(self) -> None:
        """Always shows how many characters the name has; orange and OK greyed out while it cannot be used."""
        text = self.name.text().strip()
        ok = valid_project_name(text)
        count = f"{len(text)} of {PROJECT_NAME_MAX} characters"
        if len(text) > PROJECT_NAME_MAX:
            msg = f"Too long: {count}. Project names can be up to {PROJECT_NAME_MAX} characters."
        elif text and not ok:
            msg = f"Project names can only use letters, numbers, - and _ (no spaces). {count}."
        else:
            msg = f"Letters, numbers, - and _ only (no spaces). {count}."
        self.name_hint.setText(msg)
        self.name_hint.setStyleSheet("color: #8a8a94;" if ok or not text else "color: #ff9828;")
        self.ok.setEnabled(ok)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Parent folder", self.folder.text())
        if folder:
            self.folder.setText(folder)


def ask(parent: QWidget, name: str, folder: str) -> tuple[str, str] | None:
    """Show the box. Returns (name, parent folder) or None if cancelled."""
    d = SaveAsDialog(parent, name, folder)
    if d.exec() != QDialog.Accepted:
        return None
    return d.name.text().strip(), d.folder.text().strip()
