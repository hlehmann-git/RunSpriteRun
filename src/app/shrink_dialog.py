"""Edit > Shrink Sprite: choose how small every frame of the open project becomes, as a percentage of its size.
The window shows the original and the new size in pixels. It cannot be undone (see the warning in the window)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.core.shrink import MSG_TOO_SMALL, SHRINK_PERCENTS, can_shrink, new_size, percent_label

WARNING = "This cannot be undone. Do not save the project if you want to protect the original assets."


class ShrinkDialog(QDialog):
    def __init__(self, parent: QWidget, width: int, height: int) -> None:
        super().__init__(parent)
        self.setWindowTitle("Shrink Sprite")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self.setMinimumWidth(420)
        self.width_px, self.height_px = width, height
        intro = QLabel("Every frame of this project is made smaller by the same amount. Pixels are averaged and then "
                       "matched to the colours the project already uses.")
        intro.setWordWrap(True)
        self.size_box = QComboBox()
        for pct in SHRINK_PERCENTS:
            self.size_box.addItem(f"{percent_label(pct)} of the original size", pct)
        self.size_box.setCurrentIndex(self.size_box.findData(50))
        self.original = QLabel(f"{width} x {height} pixels")
        self.new = QLabel("")
        grid = QGridLayout()
        grid.addWidget(QLabel("Shrink to"), 0, 0)
        grid.addWidget(self.size_box, 0, 1)
        grid.addWidget(QLabel("Original size"), 1, 0)
        grid.addWidget(self.original, 1, 1)
        grid.addWidget(QLabel("New size"), 2, 0)
        grid.addWidget(self.new, 2, 1)
        grid.setColumnStretch(1, 1)
        self.warning = QLabel(WARNING)
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet("color: #ff9828; font-weight: 600;")
        self.problem = QLabel("")
        self.problem.setWordWrap(True)
        self.problem.setStyleSheet("color: #ff9828;")
        self.ok = QPushButton("OK")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.ok)
        row.addWidget(cancel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.addWidget(intro)
        layout.addSpacing(8)
        layout.addLayout(grid)
        layout.addSpacing(8)
        layout.addWidget(self.warning)
        layout.addWidget(self.problem)
        layout.addStretch()
        layout.addLayout(row)
        self.size_box.currentIndexChanged.connect(self._refresh)
        self._refresh()

    def percent(self) -> float:
        return self.size_box.currentData()

    def _refresh(self) -> None:
        pct = self.percent()
        w, h = new_size(self.width_px, self.height_px, pct)
        self.new.setText(f"{w} x {h} pixels")
        ok = can_shrink(self.width_px, self.height_px, pct)
        self.ok.setEnabled(ok)
        self.problem.setText("" if ok else MSG_TOO_SMALL)
