"""Start Project dialog (section 5.3)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QPushButton, QRadioButton, QButtonGroup, QSpinBox, QToolTip, QVBoxLayout,
                               QWidget, QAbstractItemView)

from PIL import Image

from src.app import messages
from src.app.blank_sheet_dialog import ColourField
from src.core.factory import create_project
from src.core.importer import ACCEPTED_SUFFIXES, import_files, msg_frame_limit, msg_size, natural_key, read_size
from src.core import sheet_import
from src.core.project import Project
from src.core.rules import DEFAULT_FPS, FPS_CHOICES, MAX_FRAMES, MAX_SIZE, MIN_SIZE, valid_project_name
from src.core.systems import SYSTEMS, get_system
from src.io import paths
from src.io.project_file import ProjectFileError, open_project

DEFAULT_SYSTEM = "Atari ST"
NAME_HINT = "Letters, numbers, - and _ only (no spaces), 1 to 40 characters"
NAME_ERROR = "Project names can only use letters, numbers, - and _ (no spaces)."
GREY = "color: #8a8a94;"
SHEET_INFO = ("Importing a sprite sheet will save that sheet into the project folder, and also extract all sprites "
              "within the bounding boxes as sprites for your project, these will be saved in the sprites folder - "
              "this can only be done ONCE per new project. Lorem ipsum")


class InfoButton(QPushButton):
    """A small square button with a lower-case i. Hovering over it opens a narrow, portrait info box to its right."""
    BOX_WIDTH = 220

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__("i", parent)
        self.setFixedSize(24, 24)
        self.setFocusPolicy(Qt.NoFocus)
        self.box = QLabel(text, parent)
        self.box.setWordWrap(True)
        self.box.setFixedWidth(self.BOX_WIDTH)
        self.box.setMargin(8)
        self.box.setStyleSheet("background:#2b2d35; color:#e6e8ee; border:1px solid #8a8a94;")
        self.box.adjustSize()
        self.box.hide()
        self.box.setAttribute(Qt.WA_TransparentForMouseEvents)

    def enterEvent(self, event) -> None:
        top = self.parentWidget()
        pos = self.mapTo(top, self.rect().topRight())
        self.box.move(pos.x() + 4, pos.y())
        self.box.setFixedHeight(self.box.heightForWidth(self.BOX_WIDTH))
        self.box.show()
        self.box.raise_()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.box.hide()
        super().leaveEvent(event)


class StartProjectDialog(QDialog):
    """Modal. On accept, `self.project` holds the new or opened project."""

    def __init__(self, parent: QWidget | None = None, folder: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Start Project")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.project: Project | None = None
        self._folder = folder or str(paths.home_folder())      # image files: the program home folder
        self._files: list[Path] = []
        self._sizes: list[tuple[int, int] | None] = []
        self._sheet_path: Path | None = None
        self._sheet_image: Image.Image | None = None
        self._grid = sheet_import.SheetGrid()
        self._build()
        self._refresh()
        self.setFixedSize(560, 760)                  # not resizable

    # ---- layout -------------------------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        root.addLayout(grid)

        grid.addWidget(QLabel("Project name"), 0, 0)
        self.name = QLineEdit()
        self.name.setMaxLength(60)               # longer entries are flagged, not silently cut
        self.name.textChanged.connect(self._refresh)
        grid.addWidget(self.name, 0, 1)
        self.name_hint = QLabel(NAME_HINT)
        self.name_hint.setStyleSheet(GREY)
        grid.addWidget(self.name_hint, 1, 1)

        heading = QLabel("<b>Frame/Sprite Dimensions</b>")
        grid.addWidget(heading, 2, 0, 1, 2)
        row = QHBoxLayout()
        self.from_files = QCheckBox("Set from imported files")
        self.from_files.setChecked(True)
        self.from_files.toggled.connect(self._refresh)
        row.addWidget(self.from_files)
        row.addSpacing(8)
        note = QLabel("Size is read from the files. All files must be the same size.")
        note.setStyleSheet(GREY)
        row.addWidget(note, 1)
        grid.addLayout(row, 3, 0, 1, 2)

        dims = QHBoxLayout()
        dims.addWidget(QLabel("Frame width (4-64)"))
        self.width_box = QSpinBox()
        self.height_box = QSpinBox()
        for box in (self.width_box, self.height_box):
            box.setRange(MIN_SIZE, MAX_SIZE)
            box.setValue(MAX_SIZE)
            box.setButtonSymbols(QSpinBox.NoButtons)
            box.setAlignment(Qt.AlignCenter)
            box.setFixedWidth(64)
        dims.addSpacing(8)
        dims.addWidget(self.width_box)
        dims.addSpacing(16)
        dims.addWidget(QLabel("Frame height (4-64)"))
        dims.addSpacing(8)
        dims.addWidget(self.height_box)
        dims.addStretch(1)
        grid.addLayout(dims, 4, 0, 1, 2)

        grid.addWidget(QLabel("Target system"), 5, 0)
        self.system = QComboBox()
        for s in SYSTEMS:
            self.system.addItem(s.name)
        self.system.setCurrentText(DEFAULT_SYSTEM)
        self.system.currentTextChanged.connect(self._refresh)
        grid.addWidget(self.system, 5, 1)

        details = QGroupBox("System details")
        details.setStyleSheet("QGroupBox, QLabel { color: #8a8a94; }")
        d = QGridLayout(details)
        d.setContentsMargins(16, 16, 16, 12)
        d.setVerticalSpacing(10)
        self._detail_values: dict[str, QLabel] = {}
        for i, key in enumerate(("Max sprite colours", "Bits per channel", "Colour depth", "Total palette colours")):
            value = QLabel()
            d.addWidget(QLabel(key), i // 2, (i % 2) * 2)
            d.addWidget(value, i // 2, (i % 2) * 2 + 1)
            self._detail_values[key] = value
        grid.addWidget(details, 6, 0, 1, 2)

        grid.addWidget(QLabel("Frames per second"), 7, 0)
        fps_row = QHBoxLayout()
        self.fps = QComboBox()
        for f in FPS_CHOICES:
            self.fps.addItem(str(f), f)
        self.fps.setCurrentText(str(DEFAULT_FPS))
        fps_row.addWidget(self.fps)
        fps_row.addStretch(1)
        grid.addLayout(fps_row, 7, 1)

        self.sheet_radio = QRadioButton("Import sprite sheet")
        sheet_label = self.sheet_radio
        self.sheet_browse = QPushButton("Browse...")
        self.sheet_browse.clicked.connect(self._browse_sheet)
        self.sheet_info = InfoButton(SHEET_INFO, self)
        sheet_row = QHBoxLayout()
        sheet_row.setContentsMargins(0, 0, 0, 0)
        sheet_row.setSpacing(8)
        sheet_row.addWidget(sheet_label)
        sheet_row.addWidget(self.sheet_browse)
        sheet_row.addWidget(self.sheet_info)
        sheet_row.addStretch(1)
        grid.addLayout(sheet_row, 8, 0, 1, 2)
        colours_row = QHBoxLayout()
        colours_row.setSpacing(8)
        colours_row.addWidget(QLabel("Box colour"))
        self.box_colour = ColourField(self, (0, 255, 0))
        colours_row.addWidget(self.box_colour)
        colours_row.addSpacing(8)
        colours_row.addWidget(QLabel("Fill colour"))
        self.fill_colour = ColourField(self, (255, 255, 255))
        colours_row.addWidget(self.fill_colour)
        colours_row.addStretch(1)
        grid.addLayout(colours_row, 9, 0, 1, 2)
        for f in (self.box_colour, self.fill_colour):
            f.hex.editingFinished.connect(self._sheet_colours)
            f.swatch.clicked.connect(self._sheet_colours)
        self.sheet_hint = QLabel("PNG, BMP or GIF. Boxes are found by their colour; empty boxes are left out.")
        self.sheet_hint.setStyleSheet(GREY)
        grid.addWidget(self.sheet_hint, 10, 0, 1, 2)

        self.files_radio = QRadioButton("Import image files")
        self.files_radio.setChecked(True)
        files_label = self.files_radio
        self.mode = QButtonGroup(self)
        self.mode.addButton(self.sheet_radio)
        self.mode.addButton(self.files_radio)
        self.sheet_radio.toggled.connect(self._mode_changed)
        self.browse = QPushButton("Browse...")
        self.browse.clicked.connect(self._browse)
        gap = 8                                      # space between the label and the Browse button
        browse_row = QHBoxLayout()
        browse_row.setContentsMargins(0, 0, 0, 0)
        browse_row.setSpacing(gap)
        browse_row.addWidget(files_label)
        browse_row.addWidget(self.browse)
        browse_row.addStretch(1)
        grid.addLayout(browse_row, 11, 0, 1, 2)
        hint = QLabel("PNG, BMP or GIF, up to 120 files. Ctrl+click or Shift+click to pick files.")
        hint.setStyleSheet(GREY)
        hint.setContentsMargins(files_label.sizeHint().width() + gap, 0, 0, 0)   # lines up under Browse
        grid.addWidget(hint, 12, 0, 1, 2)

        root.addSpacing(4)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.file_list.setMinimumHeight(150)
        root.addWidget(self.file_list)
        self.summary = QLabel()
        root.addWidget(self.summary)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.create_btn = QPushButton("Create Project")
        self.create_btn.setDefault(True)
        self.open_btn = QPushButton("Open Project...")
        self.cancel_btn = QPushButton("Cancel")
        for b in (self.create_btn, self.open_btn, self.cancel_btn):
            buttons.addWidget(b)
        root.addLayout(buttons)
        self.create_btn.clicked.connect(self._create)
        self.open_btn.clicked.connect(self._open)
        self.cancel_btn.clicked.connect(self.reject)

    # ---- state --------------------------------------------------------------------------
    def selected_system(self):
        return get_system(self.system.currentText())

    def files(self) -> list[Path]:
        return list(self._files)

    def set_files(self, paths: list[Path]) -> None:
        """Replace the selection (Browse again replaces it). Shown in natural file-name order."""
        self._clear_sheet()
        self._files = sorted((Path(p) for p in paths if Path(p).suffix.lower() in ACCEPTED_SUFFIXES),
                             key=natural_key)
        self._sizes = [read_size(p) for p in self._files]
        self.file_list.clear()
        self.file_list.addItems([p.name for p in self._files])
        self._refresh()

    def _found_size(self) -> tuple[int, int] | None:
        """The one size shared by every readable file, or None if they differ or there are none."""
        sizes = {s for s in self._sizes if s is not None}
        return sizes.pop() if len(sizes) == 1 else None

    def _refresh(self) -> None:
        s = self.selected_system()
        vals = self._detail_values
        vals["Max sprite colours"].setText(str(s.max_colours))
        vals["Bits per channel"].setText(str(s.bits))
        vals["Colour depth"].setText(s.depth_label)
        vals["Total palette colours"].setText(f"{s.total_colours:,}")

        text = self.name.text()
        name_ok = valid_project_name(text)
        if text and not name_ok:
            self.name_hint.setText(NAME_ERROR)
            self.name_hint.setStyleSheet("color: #e5736b;")
        else:
            self.name_hint.setText(NAME_HINT)
            self.name_hint.setStyleSheet(GREY)

        sheet = self.sheet_mode()
        for w_ in (self.sheet_browse, self.box_colour, self.fill_colour, self.sheet_hint):
            w_.setEnabled(sheet)
        self.browse.setEnabled(not sheet)
        self.from_files.setEnabled(not sheet)
        auto = self.from_files.isChecked() or sheet
        self.width_box.setEnabled(not auto)
        self.height_box.setEnabled(not auto)
        found = self._found_size()
        if self._sheet_image is not None and not self._grid.error:
            found = (self._grid.width, self._grid.height)
        if auto and found and MIN_SIZE <= found[0] <= MAX_SIZE and MIN_SIZE <= found[1] <= MAX_SIZE:
            self.width_box.setValue(found[0])
            self.height_box.setValue(found[1])

        n = len(self._files)
        if sheet:
            if self._sheet_image is None:
                self.summary.setText("No sprite sheet selected")
                self.create_btn.setEnabled(False)
                return
            if self._grid.error:
                self.summary.setText(f"{self._sheet_path.name}: {self._grid.error}")
            else:
                self.summary.setText(f"{self._sheet_path.name}: {len(self._grid.boxes)} boxes, "
                                     f"each {self._grid.width} x {self._grid.height}")
            self.create_btn.setEnabled(name_ok and not self._grid.error)
            return
        if n == 0:
            self.summary.setText("No files selected")
        elif found:
            self.summary.setText(f"{n} file{'s' if n != 1 else ''} selected, all {found[0]} x {found[1]}")
        else:
            self.summary.setText(f"{n} file{'s' if n != 1 else ''} selected, sizes differ")
        self.create_btn.setEnabled(name_ok and n > 0)

    # ---- actions ------------------------------------------------------------------------
    def _browse(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(
            self, "Select image files", self._folder, "Images (*.png *.bmp *.gif)")
        if names:
            self._folder = str(Path(names[0]).parent)
            self.set_files([Path(n) for n in names])

    def sheet_mode(self) -> bool:
        return self.sheet_radio.isChecked()

    def _mode_changed(self) -> None:
        """Only one of the two ways to bring sprites in is active; the other one is cleared and greyed out."""
        if self.sheet_mode():
            self._files, self._sizes = [], []
            self.file_list.clear()
        else:
            self._clear_sheet()
            self._sizes = []
            self.file_list.clear()
        self._refresh()

    def _clear_sheet(self) -> None:
        self._sheet_path = None
        self._sheet_image = None
        self._grid = sheet_import.SheetGrid()

    def _browse_sheet(self) -> None:
        name, _ = QFileDialog.getOpenFileName(
            self, "Select sprite sheet", self._folder, "Images (*.png *.bmp *.gif)")
        if name:
            self._folder = str(Path(name).parent)
            self.set_sheet(Path(name))

    def set_sheet(self, path: Path) -> None:
        """Choose a sprite sheet. It replaces any image files already chosen."""
        try:
            with Image.open(path) as im:
                im.load()
                if getattr(im, "n_frames", 1) > 1:
                    messages.warn(self, "Animated GIFs are not supported.")
                    return
                self._sheet_image = im.copy()
        except (OSError, ValueError, SyntaxError):
            messages.warn(self, f"{Path(path).name} could not be read.")
            return
        self._files, self._sizes = [], []
        self._sheet_path = Path(path)
        self._scan_sheet()

    def _sheet_colours(self) -> None:
        if self._sheet_image is not None:
            self._scan_sheet()

    def _scan_sheet(self) -> None:
        self._grid = sheet_import.find_grid(self._sheet_image, self.box_colour.colour)
        self.file_list.clear()
        if not self._grid.error:
            self.file_list.addItems([f"Box {n}" for n in range(1, len(self._grid.boxes) + 1)])
            self._sizes = [(self._grid.width, self._grid.height)]
        else:
            self._sizes = []
        self._refresh()

    def _frame_size(self) -> tuple[int, int] | None:
        """The size to use, or None after showing the message that blocks Create Project."""
        if not self.from_files.isChecked():
            return self.width_box.value(), self.height_box.value()
        first = next((s for s in self._sizes if s is not None), None)
        if first is None:
            return self.width_box.value(), self.height_box.value()   # nothing readable: import reports it
        w, h = first
        if not (MIN_SIZE <= w <= MAX_SIZE and MIN_SIZE <= h <= MAX_SIZE):
            lines = [f"{p.name} is {s[0]} x {s[1]}. Frame sizes must be {MIN_SIZE} to {MAX_SIZE} pixels."
                     for p, s in zip(self._files, self._sizes) if s is not None
                     and not (MIN_SIZE <= s[0] <= MAX_SIZE and MIN_SIZE <= s[1] <= MAX_SIZE)]
            messages.warn(self, "\n".join(lines[:20]))
            return None
        return w, h

    def _create_from_sheet(self) -> None:
        g = self._grid
        if self.box_colour.colour == self.fill_colour.colour:
            messages.warn(self, "The box colour and the fill colour must be different.")
            return
        system = self.selected_system()
        result = sheet_import.import_sheet(self._sheet_image, self._sheet_path.stem, g,
                                           self.fill_colour.colour, system)
        if result.rejected:
            messages.warn(self, result.rejected)
            return
        if result.skipped:
            lines = "\n".join(f"{s.file}: {s.reason}" for s in result.skipped)
            if not result.frames:
                messages.warn(self, "No valid sprites are left, so no project was created.", lines)
                return
            if not messages.choose(self, "Some sprites cannot be imported.", lines,
                                   "Continue without these sprites", "Back"):
                return
        if result.adjustments:
            lines = [f"{a.count} colours in {a.file} were adjusted to the nearest colour valid for {system.name}."
                     for a in result.adjustments]
            details = "\n".join(f"{a.file}: " + ", ".join(f"{o} -> {n}" for o, n in a.details)
                                for a in result.adjustments)
            messages.adjusted(self, lines, details)
        self.project = create_project(self.name.text(), system, g.width, g.height, result, self.fps.currentData())
        self.project.transparent = self.fill_colour.colour
        self.project.source_sheet = str(self._sheet_path)
        self.accept()

    def _create(self) -> None:
        if self.sheet_mode():
            self._create_from_sheet()
            return
        size = self._frame_size()
        if size is None:
            return
        w, h = size
        system = self.selected_system()
        result = import_files(self._files, system, w, h)

        if result.rejected:
            messages.warn(self, result.rejected)
            return
        if result.size_errors:
            messages.warn(self, "\n".join(result.size_errors[:30]),
                          None if len(result.size_errors) <= 30 else f"...and {len(result.size_errors) - 30} more.")
            return
        if result.skipped:
            lines = "\n".join(f"{s.file}: {s.reason}" for s in result.skipped)
            if not result.frames:
                messages.warn(self, "No valid files are left, so no project was created.", lines)
                return
            if not messages.choose(self, "Some files cannot be imported.", lines,
                                   "Continue without these files", "Back"):
                return
        if not result.frames:
            messages.warn(self, "No valid files are left, so no project was created.")
            return
        if result.adjustments:
            lines = [a_msg for a_msg in
                     (f"{a.count} colours in {a.file} were adjusted to the nearest colour valid for {system.name}."
                      for a in result.adjustments)]
            details = "\n".join(f"{a.file}: " + ", ".join(f"{o} -> {n}" for o, n in a.details)
                                for a in result.adjustments)
            messages.adjusted(self, lines, details)

        self.project = create_project(self.name.text(), system, w, h, result, self.fps.currentData())
        self.accept()

    def _open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", str(paths.projects_folder()), "RunSpriteRun projects (*.rsr)")
        if path:
            self.open_path(Path(path))

    def open_path(self, path: Path) -> None:
        """Open a saved project. A damaged file shows the PRD message and the dialog stays."""
        try:
            self.project = open_project(path)
        except ProjectFileError:
            messages.warn(self, f"{path.name} could not be opened. It may be damaged or saved by a "
                                "different version of RunSpriteRun.")
            return
        self.accept()
