"""Edit > Reduce Palette: choose how many colours the project keeps. A From / To window shows the result for any frame
before anything is changed. It cannot be undone (see the warning in the window)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from src.app.render import scaled_sprite, to_qimage
from src.app.shrink_dialog import WARNING
from src.core.project import Project
from src.core.reduce_palette import colour_count, colour_counts, make_mapping, remap_image, target_range

VIEW = 200


class ReduceDialog(QDialog):
    def __init__(self, parent: QWidget, project: Project, frame: int = 0) -> None:
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Reduce Palette")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self.counts = colour_counts(project)
        self.current = colour_count(project)
        lo, hi = target_range(project)
        self._maps: dict[int, dict] = {}
        intro = QLabel("The program keeps the colours that matter most to the picture and changes every other pixel to the "
                       "nearest colour that stays. The transparent colour is always kept and is not counted.")
        intro.setWordWrap(True)
        self.target = QSpinBox()
        self.target.setRange(lo, hi)
        self.target.setValue(max(lo, min(hi, self.current // 2)))
        self.frame_box = QSpinBox()
        self.frame_box.setRange(1, len(project.frames))
        self.frame_box.setValue(frame + 1)
        self.summary = QLabel("")
        self.from_view, self.to_view = QLabel(), QLabel()
        for v in (self.from_view, self.to_view):
            v.setFixedSize(VIEW, VIEW)
            v.setAlignment(Qt.AlignCenter)
            v.setStyleSheet("background: #000;")
        grid = QGridLayout()
        grid.addWidget(QLabel("Colours to keep"), 0, 0)
        grid.addWidget(self.target, 0, 1)
        grid.addWidget(QLabel("Preview frame"), 1, 0)
        grid.addWidget(self.frame_box, 1, 1)
        grid.setColumnStretch(2, 1)
        views = QGridLayout()
        views.addWidget(QLabel("From"), 0, 0, Qt.AlignCenter)
        views.addWidget(QLabel("To"), 0, 1, Qt.AlignCenter)
        views.addWidget(self.from_view, 1, 0)
        views.addWidget(self.to_view, 1, 1)
        warning = QLabel(WARNING)
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #ff9828; font-weight: 600;")
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
        for w in (intro,):
            layout.addWidget(w)
        layout.addLayout(grid)
        layout.addWidget(self.summary)
        layout.addLayout(views)
        layout.addWidget(warning)
        layout.addLayout(row)
        self.target.valueChanged.connect(self._refresh)
        self.frame_box.valueChanged.connect(self._refresh)
        self._refresh()

    def keep(self) -> int:
        return self.target.value()

    def mapping(self, keep: int) -> dict:
        if keep not in self._maps:
            self._maps[keep] = make_mapping(self.counts, keep)
        return self._maps[keep]

    def _show(self, label: QLabel, img) -> None:
        big = scaled_sprite(img, self.project.transparent, VIEW, VIEW, False)
        label.setPixmap(QPixmap.fromImage(to_qimage(big)))

    def _refresh(self) -> None:
        keep = self.keep()
        self.summary.setText(f"{self.current} colours now, {keep} after: {self.project.system.max_colours - 1 - keep} "
                             f"places free for other colours.")
        frame = self.project.frames[self.frame_box.value() - 1]
        self._show(self.from_view, frame.image)
        self._show(self.to_view, remap_image(frame.image, self.mapping(keep)))
