"""The Export window (FR-4.7): one window, no choices to make except the folder and the fill colour.
Everything is exported: the all-frames sheet, a sheet for every Frame Group and every frame as a PNG, into a new
folder named after the project inside the chosen folder."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget)

from src.app import messages
from src.core import colour as colour_rules
from src.core.project import Project
from src.io import export, paths

MSG_OUTSIDE = "Choose a folder outside your project folders."


def confirm_replace(parent: QWidget, files: list[str]) -> bool:
    """Existing files prompt (5.5): lists the files, Replace all or Cancel."""
    box = QMessageBox(QMessageBox.Question, "RunSpriteRun",
                      f"{len(files)} file(s) already exist in this folder. Replace them?", QMessageBox.NoButton, parent)
    box.setDetailedText("\n".join(files))
    yes = box.addButton("Replace all", QMessageBox.AcceptRole)
    box.addButton("Cancel", QMessageBox.RejectRole)
    box.exec()
    return box.clickedButton() is yes


class ExportDialog(QDialog):
    def __init__(self, parent: QWidget, project: Project) -> None:
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Export")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(480)

        box = QGroupBox("What will be written")
        grid = QGridLayout(box)
        self.colours = QLabel()
        self.frames = QLabel()
        self.groups = QLabel()
        self.sheets = QLabel()
        self.largest = QLabel()
        for r, c, label, widget in ((0, 0, "Colours", self.colours), (0, 2, "Frames", self.frames),
                                    (0, 4, "Frame Groups", self.groups), (1, 0, "Sheets", self.sheets),
                                    (1, 2, "Largest sheet", self.largest)):
            grid.addWidget(QLabel(label), r, c)
            grid.addWidget(widget, r, c + 1)

        self.folder = QLineEdit(str(paths.exports_folder()))
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Folder"))
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(browse)
        self.hint = QLabel()
        self.hint.setStyleSheet("color: #9aa0ae;")

        self.fill = QComboBox()
        self.fill.addItem("Transparent colour", project.transparent)
        for c in project.palette():
            if c != project.transparent:
                self.fill.addItem(colour_rules.to_hex(c), c)
        options = QGridLayout()
        options.addWidget(QLabel("Fill colour"), 0, 0)
        options.addWidget(self.fill, 0, 1)
        options.setColumnStretch(2, 1)

        self.result = QLabel("")
        self.result.setStyleSheet("color: #9aa0ae;")
        self.export_button = QPushButton("Export")
        self.export_button.setDefault(True)
        self.export_button.clicked.connect(self.run_export)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.export_button)
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(box)
        layout.addLayout(folder_row)
        layout.addWidget(self.hint)
        layout.addLayout(options)
        layout.addWidget(self.result)
        layout.addLayout(buttons)
        self.folder.textChanged.connect(self._hint)
        self._summary()
        self._hint()

    def _summary(self) -> None:
        p = self.project
        self.colours.setText(str(p.colours_in_use()))
        self.frames.setText(str(len(p.frames)))
        self.groups.setText(str(len(p.groups)))
        self.sheets.setText(str(export.sheet_count(p)))
        w, h = export.largest_sheet(p)
        self.largest.setText(f"{w} x {h} px")

    def _hint(self) -> None:
        self.hint.setText(f"Writes three folders into {self.target()}")

    def target(self) -> Path:
        return Path(self.folder.text().strip() or str(paths.exports_folder())) / self.project.name

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose a folder", self.folder.text())
        if chosen:
            self.folder.setText(chosen)

    def run_export(self) -> bool:
        p = self.project
        parent = Path(self.folder.text().strip() or str(paths.exports_folder()))
        if export.inside_project_folder(parent, p):
            messages.warn(self, MSG_OUTSIDE)
            return False
        target = self.target()
        files = export.planned_files(p, with_data=False)
        clash = export.existing_files(target, files)
        if clash and not confirm_replace(self, clash):
            return False
        try:
            written = export.write_all(p, target, self.fill.currentData(), with_data=False)
        except OSError as e:
            messages.warn(self, f"The files could not be written. {e.strerror or e}")
            return False
        self.result.setText(f"Exported {len(p.frames)} frames and {export.sheet_count(p)} sheets to {target}")
        self.written = written
        return True
