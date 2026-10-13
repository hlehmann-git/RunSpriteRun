"""The Create Blank Sprite Sheet window (FR-4.9): choose the system, the sprite size, the grid and the two colours,
then Create. It works with or without a project and never changes one."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

from src.app import messages
from src.app.export_dialog import confirm_replace
from src.core import blank_sheet
from src.core import colour as colour_rules
from src.core.rules import MAX_FRAMES, MAX_SIZE, MIN_SIZE
from src.core.systems import SYSTEMS, get_system
from src.io import blank_file


class ColourField(QWidget):
    """A colour square (click it to pick) and its hex code."""

    def __init__(self, parent: QWidget, start: tuple[int, int, int]) -> None:
        super().__init__(parent)
        self.colour = start
        self.swatch = QPushButton()
        self.swatch.setFixedSize(24, 24)
        self.swatch.clicked.connect(self._pick)
        self.hex = QLineEdit(colour_rules.to_hex(start))
        self.hex.setMaxLength(7)
        self.hex.setFixedWidth(90)
        self.hex.editingFinished.connect(self._typed)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.swatch)
        row.addWidget(self.hex)
        row.addStretch()
        self._paint()

    def set_colour(self, c: tuple[int, int, int]) -> None:
        self.colour = c
        self.hex.setText(colour_rules.to_hex(c))
        self._paint()

    def _paint(self) -> None:
        self.swatch.setStyleSheet(f"background:{colour_rules.to_hex(self.colour)}; border:1px solid #e6e8ee;")

    def _typed(self) -> None:
        c = colour_rules.parse_hex(self.hex.text())
        if c is None:
            self.hex.setText(colour_rules.to_hex(self.colour))      # not six hex digits: put the old code back
        else:
            self.set_colour(c)

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(QColor(*self.colour), self, "Choose a colour")
        if chosen.isValid():
            self.set_colour((chosen.red(), chosen.green(), chosen.blue()))


class BlankSheetDialog(QDialog):
    def __init__(self, parent: QWidget, base=None) -> None:
        super().__init__(parent)
        self.base = base                                   # folder to save into; None means Blank sprite sheets in home
        self.setWindowTitle("Create Blank Sprite Sheet")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(480)

        self.system = QComboBox()
        for s in SYSTEMS:
            self.system.addItem(s.name, s.name)
        self.system.setCurrentIndex(self.system.findData("Atari ST"))
        self.width_box = self._spin(MIN_SIZE, MAX_SIZE, 32)
        self.height_box = self._spin(MIN_SIZE, MAX_SIZE, 32)
        self.per_row = self._spin(1, MAX_FRAMES, 10)
        self.rows = self._spin(1, MAX_FRAMES, 4)
        self.box_colour = ColourField(self, blank_sheet.DEFAULT_BOX)
        self.fill_colour = ColourField(self, blank_sheet.DEFAULT_FILL)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        note = lambda t: self._note(t)
        rows = (("System", self.system, None), ("Sprite width (4-64 px)", self.width_box, None),
                ("Sprite height (4-64 px)", self.height_box, None), ("Sprites per row", self.per_row, None),
                ("Number of rows", self.rows, None), ("Box colour", self.box_colour, note("Not used in the sprites")),
                ("Fill colour", self.fill_colour, note("Empty box inside")))
        for r, (label, widget, extra) in enumerate(rows):
            grid.addWidget(QLabel(label), r, 0)
            grid.addWidget(widget, r, 1, Qt.AlignLeft)
            if extra is not None:
                grid.addWidget(extra, r, 2)
        grid.setColumnStretch(2, 1)

        self.summary = self._note("")
        self.hint = self._note("")
        self.result = self._note("")
        self.create_button = QPushButton("Create")
        self.create_button.setDefault(True)
        self.create_button.clicked.connect(self.create)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.create_button)
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addLayout(grid)
        layout.addWidget(self.summary)
        layout.addWidget(self.hint)
        layout.addWidget(self.result)
        layout.addLayout(buttons)
        for w in (self.width_box, self.height_box, self.per_row, self.rows):
            w.valueChanged.connect(self._update)
        self.system.currentIndexChanged.connect(self._update)
        self._update()

    @staticmethod
    def _spin(lo: int, hi: int, value: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(value)
        s.setFixedWidth(72)
        return s

    @staticmethod
    def _note(text: str) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet("color: #9aa0ae;")
        return lab

    def settings(self):
        return (get_system(self.system.currentData()), self.width_box.value(), self.height_box.value(),
                self.per_row.value(), self.rows.value())

    def _update(self) -> None:
        system, w, h, per_row, rows = self.settings()
        sw, sh = blank_sheet.sheet_size(w, h, per_row, rows)
        self.summary.setText(f"Sheet: {sw} x {sh} px, {per_row * rows} sprites ({per_row} per row, {rows} rows)")
        self.hint.setText(f"Saved into Blank sprite sheets\\{blank_sheet.system_folder(system)}")

    def create(self) -> bool:
        system, w, h, per_row, rows = self.settings()
        box, fill = self.box_colour.colour, self.fill_colour.colour
        problem = blank_sheet.problem(w, h, per_row, rows, box, fill)
        if problem:
            messages.warn(self, problem)
            return False
        path = blank_file.target_path(system, w, h, per_row, rows, self.base)
        if path.exists() and not confirm_replace(self, [path.name]):
            return False
        try:
            path = blank_file.write(system, w, h, per_row, rows, box, fill, self.base)
        except OSError as e:
            messages.warn(self, f"The files could not be written. {e.strerror or e}")
            return False
        self.result.setText(f"Saved {path}")
        self.saved = path
        return True
