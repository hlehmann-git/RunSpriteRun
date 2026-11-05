"""Edit > Resize Canvas (v2.0.20): choose a new canvas size for every frame. Before / After pictures show the result on
any frame, at the same zoom so the change in size can be seen. A size that would cut off drawn pixels is refused here
(red message, OK greyed out); the smallest size that keeps every sprite whole is shown."""
from __future__ import annotations

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QLayout, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from src.app.render import fit_scale, to_qimage, with_checker
from src.core import canvas
from src.core.project import Project
from src.core.rules import MAX_SIZE, MIN_SIZE

VIEW = 200
GREY = "color: #9aa0ae;"
ERROR = "color: #e05a5a; font-weight: 600;"


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


class ResizeDialog(QDialog):
    def __init__(self, parent: QWidget | None, project: Project, frame: int = 0, grounded: bool = True,
                 checker: bool = False) -> None:
        super().__init__(parent)
        self.project = project
        self.checker = checker
        self.boxes = canvas.drawn_boxes(project)
        self.setWindowTitle("Resize Canvas")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setModal(True)
        intro = QLabel("Changes the canvas of every frame and every layer. Nothing is stretched: new space is filled with "
                       "the transparent colour. The canvas cannot be made smaller than the sprites already drawn.")
        intro.setWordWrap(True)
        current = QLabel(f"Current size: <b>{project.width} x {project.height}</b>")
        self.smallest = QLabel("")
        self.smallest.setStyleSheet("color: #c9ccd6;")
        self.width_box, self.height_box, self.frame_box = QSpinBox(), QSpinBox(), QSpinBox()
        for box, value in ((self.width_box, project.width), (self.height_box, project.height)):
            box.setRange(MIN_SIZE, MAX_SIZE)
            box.setValue(value)
            box.setFixedWidth(70)
        self.frame_box.setRange(1, len(project.frames))
        self.frame_box.setValue(frame + 1)
        self.frame_box.setFixedWidth(70)
        grid = QGridLayout()
        grid.addWidget(QLabel("Width"), 0, 0)
        grid.addWidget(self.width_box, 0, 1)
        grid.addWidget(QLabel("Height"), 1, 0)
        grid.addWidget(self.height_box, 1, 1)
        grid.addWidget(QLabel("Preview frame"), 2, 0)
        grid.addWidget(self.frame_box, 2, 1)
        grid.setColumnStretch(2, 1)
        self.grounded_box = QCheckBox("Keep sprite grounded")
        self.grounded_box.setChecked(grounded)
        self.grounded_hint = QLabel("")
        self.grounded_hint.setWordWrap(True)
        self.grounded_hint.setStyleSheet(GREY)
        self.change = QLabel("")
        self.change.setStyleSheet("font-weight: 600;")
        self.from_view, self.to_view = QLabel(), QLabel()
        for v in (self.from_view, self.to_view):
            v.setFixedSize(VIEW, VIEW)
            v.setAlignment(Qt.AlignCenter)
            v.setStyleSheet("background: #000; " + GREY)
        views = QGridLayout()
        views.addWidget(QLabel("Before"), 0, 0, Qt.AlignCenter)
        views.addWidget(QLabel("After"), 0, 1, Qt.AlignCenter)
        views.addWidget(self.from_view, 1, 0)
        views.addWidget(self.to_view, 1, 1)
        self.error = QLabel("")
        self.error.setWordWrap(True)
        self.error.setStyleSheet(ERROR)
        undo = QLabel("You can undo this with Ctrl+Z.")
        undo.setStyleSheet(GREY)
        self.ok = QPushButton("OK")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(undo)
        row.addStretch()
        row.addWidget(self.ok)
        row.addWidget(cancel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        for w in (intro, current, self.smallest):
            layout.addWidget(w)
        layout.addLayout(grid)
        layout.addWidget(self.grounded_box)
        layout.addWidget(self.grounded_hint)
        layout.addWidget(self.change)
        layout.addLayout(views)
        layout.addWidget(self.error)
        layout.addLayout(row)
        for label in (intro, self.grounded_hint, self.error):
            label.setFixedWidth(2 * VIEW + 24)                # wrapped text keeps the width of the two pictures
        layout.setSizeConstraint(QLayout.SetFixedSize)        # the window grows to fit, so nothing overlaps
        for box in (self.width_box, self.height_box, self.frame_box):
            box.valueChanged.connect(self._refresh)
        self.grounded_box.toggled.connect(self._refresh)
        self._refresh()

    def chosen_size(self) -> tuple[int, int]:
        return self.width_box.value(), self.height_box.value()

    def grounded(self) -> bool:
        return self.grounded_box.isChecked()

    def _picture(self, img: Image.Image, scale: int) -> QPixmap:
        big = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        if self.checker:
            big = with_checker(big, img, self.project.transparent, scale)
        out = Image.new("RGB", (VIEW, VIEW), (0, 0, 0))
        out.paste(big, ((VIEW - big.width) // 2, (VIEW - big.height) // 2))
        return QPixmap.fromImage(to_qimage(out))

    def _refresh(self) -> None:
        p = self.project
        w, h = self.chosen_size()
        grounded = self.grounded()
        self.grounded_hint.setText("The bottom edge stays put: new height is added at the top, and a smaller height "
                                   "comes off the top." if grounded else
                                   "The sprite stays centred; an odd extra pixel goes on the right or the bottom.")
        mw, mh = canvas.smallest_size(p, grounded, self.boxes)
        self.smallest.setText(f"Smallest size that keeps every sprite whole: <b>{mw} x {mh}</b>")
        self.change.setText(f"{p.width} x {p.height}  →  {w} x {h}   ({_signed(w - p.width)} wide, "
                            f"{_signed(h - p.height)} high)")
        why = canvas.problem(p, w, h, grounded, self.boxes)
        self.error.setText(why or "")
        self.error.setVisible(why is not None)
        self.ok.setEnabled(why is None and (w, h) != (p.width, p.height))
        img = p.frames[self.frame_box.value() - 1].image
        scale = fit_scale(max(p.width, w), max(p.height, h), VIEW, VIEW)
        self.from_view.setPixmap(self._picture(img, scale))
        if why is None:
            self.to_view.setPixmap(self._picture(canvas.place(img, w, h, p.transparent, grounded), scale))
        else:
            self.to_view.setPixmap(QPixmap())
            self.to_view.setText("No preview:\nthis size would\ncut off pixels")
