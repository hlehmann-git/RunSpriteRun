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
from src.core.rules import (DEFAULT_FPS, FPS_CHOICES, MAX_FRAMES, MAX_SIZE, MIN_SIZE, NAME_MAX, clean_name,
                            valid_name, valid_project_name)
from src.core.colour import snap_colour
from src.core.importer import ImportedFrame, ImportResult
from src.core.systems import SYSTEMS, get_system
from src.io import paths
from src.io.project_file import InvalidNameError, ProjectFileError, open_project

DEFAULT_SYSTEM = "Atari ST"
NAME_HINT = "Letters, numbers, - and _ only (no spaces), 1 to 40 characters"
NAME_ERROR = "Project names can only use letters, numbers, - and _ (no spaces)."
GREY = "color: #8a8a94;"
ORANGE = "color: #ff9828;"                    # a problem that stops Create Project
BLANK_FRAMES_DEFAULT = 12
BLANK_SIZE_DEFAULT = 32
INDENT = 24
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
        self.setFixedSize(560, self.sizeHint().height())                  # not resizable

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

        grid.addWidget(QLabel("Target system"), 2, 0)
        self.system = QComboBox()
        for s in SYSTEMS:
            self.system.addItem(s.name)
        self.system.setCurrentText(DEFAULT_SYSTEM)
        self.system.currentTextChanged.connect(self._refresh)
        grid.addWidget(self.system, 2, 1)

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
        grid.addWidget(details, 3, 0, 1, 2)

        grid.addWidget(QLabel("<b>Project Details</b>"), 4, 0, 1, 2)
        # frame size: either typed in, or taken from the imported sprites
        self.size_radio = QRadioButton("Set frame size")
        self.from_files = QRadioButton("Set from imported sprites")      # (the old tick box, now a radio)
        self.size_group = QButtonGroup(self)
        self.size_group.addButton(self.size_radio)
        self.size_group.addButton(self.from_files)
        self.size_radio.setChecked(True)
        self.width_box = QSpinBox()
        self.height_box = QSpinBox()
        for box in (self.width_box, self.height_box):
            box.setRange(MIN_SIZE, MAX_SIZE)
            box.setValue(BLANK_SIZE_DEFAULT)
            box.setButtonSymbols(QSpinBox.NoButtons)
            box.setAlignment(Qt.AlignCenter)
            box.setFixedWidth(64)
        size_row = QHBoxLayout()
        size_row.setSpacing(8)
        size_row.addWidget(self.size_radio)
        size_row.addWidget(QLabel("Width"))
        size_row.addWidget(self.width_box)
        size_row.addWidget(QLabel("Height"))
        size_row.addWidget(self.height_box)
        size_row.addWidget(QLabel(f"({MIN_SIZE}-{MAX_SIZE})"))
        size_row.addStretch(1)
        grid.addLayout(size_row, 5, 0, 1, 2)
        auto_row = QHBoxLayout()
        auto_row.setSpacing(8)
        auto_row.addWidget(self.from_files)
        self.found_label = QLabel()
        self.found_label.setStyleSheet(GREY)
        auto_row.addWidget(self.found_label, 1)
        grid.addLayout(auto_row, 6, 0, 1, 2)
        self.size_group.buttonToggled.connect(lambda *_: self._refresh())

        grid.addWidget(QLabel("Frames per second"), 7, 0)
        fps_row = QHBoxLayout()
        self.fps = QComboBox()
        for f in FPS_CHOICES:
            self.fps.addItem(str(f), f)
        self.fps.setCurrentText(str(DEFAULT_FPS))
        fps_row.addWidget(self.fps)
        fps_row.addStretch(1)
        grid.addLayout(fps_row, 7, 1)

        grid.addWidget(QLabel("<b>Starting sprites</b>"), 8, 0, 1, 2)
        self.blank_radio = QRadioButton("Blank project")
        self.blank_radio.setChecked(True)
        grid.addWidget(self.blank_radio, 9, 0, 1, 2)
        blank_row = QHBoxLayout()
        blank_row.setContentsMargins(INDENT, 0, 0, 0)
        blank_row.setSpacing(8)
        blank_row.addWidget(QLabel("Empty frames"))
        self.blank_frames = QSpinBox()
        self.blank_frames.setRange(1, MAX_FRAMES)
        self.blank_frames.setValue(BLANK_FRAMES_DEFAULT)
        self.blank_frames.setAlignment(Qt.AlignCenter)
        self.blank_frames.setFixedWidth(64)
        blank_row.addWidget(self.blank_frames)
        blank_note = QLabel(f"1 to {MAX_FRAMES}")
        blank_note.setStyleSheet(GREY)
        blank_row.addWidget(blank_note)
        blank_row.addStretch(1)
        grid.addLayout(blank_row, 10, 0, 1, 2)

        self.sheet_radio = QRadioButton("Import sprite sheet")
        self.sheet_browse = QPushButton("Browse...")
        self.sheet_browse.clicked.connect(self._browse_sheet)
        self.sheet_info = InfoButton(SHEET_INFO, self)
        sheet_row = QHBoxLayout()
        sheet_row.setContentsMargins(0, 0, 0, 0)
        sheet_row.setSpacing(8)
        sheet_row.addWidget(self.sheet_radio)
        sheet_row.addWidget(self.sheet_browse)
        sheet_row.addWidget(self.sheet_info)
        self.sheet_name = QLineEdit()                     # the chosen sheet, shown so it is clear what is being used
        self.sheet_name.setReadOnly(True)
        self.sheet_name.setPlaceholderText("No sheet chosen")
        self.sheet_name.setFocusPolicy(Qt.NoFocus)
        sheet_row.addWidget(self.sheet_name, 1)
        grid.addLayout(sheet_row, 11, 0, 1, 2)
        colours_row = QHBoxLayout()
        colours_row.setContentsMargins(INDENT, 0, 0, 0)
        colours_row.setSpacing(8)
        colours_row.addWidget(QLabel("Box colour"))
        self.box_colour = ColourField(self, (0, 255, 0))
        colours_row.addWidget(self.box_colour)
        colours_row.addSpacing(8)
        colours_row.addWidget(QLabel("Transparent colour"))
        self.fill_colour = ColourField(self, (255, 0, 255))
        colours_row.addWidget(self.fill_colour)
        colours_row.addStretch(1)
        grid.addLayout(colours_row, 12, 0, 1, 2)
        for f in (self.box_colour, self.fill_colour):
            f.hex.editingFinished.connect(self._sheet_colours)
            f.swatch.clicked.connect(self._sheet_colours)
        self.sheet_hint = QLabel("PNG, BMP or GIF. Boxes are found by their colour; empty boxes are left out.")
        self.sheet_hint.setStyleSheet(GREY)
        self.sheet_hint.setContentsMargins(INDENT, 0, 0, 0)
        name_row = QHBoxLayout()
        name_row.setContentsMargins(INDENT, 0, 0, 0)
        name_row.setSpacing(8)
        self.frame_name_label = QLabel("Frame name")
        self.frame_name = QLineEdit()                     # the frames become <name>_001, <name>_002 ...
        self.frame_name.setMaxLength(NAME_MAX - 4)        # room for the _NNN number
        self.frame_name.setPlaceholderText("e.g. Rick")
        name_row.addWidget(self.frame_name_label)
        name_row.addWidget(self.frame_name, 1)
        sheet_extra = QVBoxLayout()
        sheet_extra.setContentsMargins(0, 0, 0, 0)
        sheet_extra.setSpacing(4)
        sheet_extra.addLayout(name_row)
        sheet_extra.addWidget(self.sheet_hint)
        grid.addLayout(sheet_extra, 13, 0, 1, 2)

        self.files_radio = QRadioButton("Import image files")
        self.mode = QButtonGroup(self)
        self.mode.addButton(self.blank_radio)
        self.mode.addButton(self.sheet_radio)
        self.mode.addButton(self.files_radio)
        self.sheet_radio.toggled.connect(self._mode_changed)
        self.blank_radio.toggled.connect(self._mode_changed)
        self.browse = QPushButton("Browse...")
        self.browse.clicked.connect(self._browse)
        files_hint = QLabel("PNG, BMP or GIF, up to 120 files.")
        files_hint.setStyleSheet(GREY)
        browse_row = QHBoxLayout()
        browse_row.setContentsMargins(0, 0, 0, 0)
        browse_row.setSpacing(8)
        browse_row.addWidget(self.files_radio)
        browse_row.addWidget(self.browse)
        browse_row.addWidget(files_hint)
        browse_row.addStretch(1)
        grid.addLayout(browse_row, 14, 0, 1, 2)
        for box in (self.blank_frames, self.width_box, self.height_box):
            box.valueChanged.connect(self._refresh)

        self.file_list = QListWidget()                 # filled by the code below but not shown (no list of names)
        self.file_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.file_list.hide()
        root.addSpacing(4)
        self.summary = QLabel()
        self.summary.setStyleSheet(GREY)
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        root.addStretch(1)

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
        self.files_radio.setChecked(True)
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
        vals["Bits per channel"].setText("Not used: the colours are fixed" if s.is_fixed else str(s.bits))
        vals["Colour depth"].setText(s.depth_label)
        vals["Total palette colours"].setText(f"{s.total_colours:,}")

        text = self.name.text()
        name_ok = valid_project_name(text)
        if text and not name_ok:
            self.name_hint.setText(NAME_ERROR)
            self.name_hint.setStyleSheet(ORANGE)
        else:
            self.name_hint.setText(NAME_HINT)
            self.name_hint.setStyleSheet(GREY)

        sheet = self.sheet_mode()
        blank = self.blank_mode()
        for w_ in (self.sheet_browse, self.box_colour, self.fill_colour, self.sheet_hint,
                   self.frame_name, self.frame_name_label):
            w_.setEnabled(sheet)
        self.browse.setEnabled(not sheet and not blank)
        self.blank_frames.setEnabled(blank)
        if blank and not self.size_radio.isChecked():            # Blank: the size is always typed in
            self._set_size_radio(True)
        self.from_files.setEnabled(not blank)
        auto = self.from_files.isChecked() and not blank
        self.width_box.setEnabled(not auto)
        self.height_box.setEnabled(not auto)
        found = self._native_size()
        self.found_label.setText(f"{found[0]} x {found[1]}" if found and not blank else "")
        if auto and found and MIN_SIZE <= found[0] <= MAX_SIZE and MIN_SIZE <= found[1] <= MAX_SIZE:
            for box, v in ((self.width_box, found[0]), (self.height_box, found[1])):
                box.blockSignals(True)
                box.setValue(v)
                box.blockSignals(False)
        small = (not auto and not blank and found is not None
                 and (self.width_box.value() < found[0] or self.height_box.value() < found[1]))
        self.summary.setStyleSheet(ORANGE if small else GREY)

        n = len(self._files)
        if blank:
            taken = self._blank_folder_taken()
            self.summary.setStyleSheet(ORANGE if taken else GREY)
            self.summary.setText(f"A project called {text} already exists in the Projects folder. Choose another name."
                                 if taken else f"{self.blank_frames.value()} empty frames, "
                                 f"{self.width_box.value()} x {self.height_box.value()}")
            self.create_btn.setEnabled(name_ok and not taken)
            return
        if small:
            self.summary.setText(f"The sprites are {found[0]} x {found[1]}, so the frame size must be at least "
                                 f"{found[0]} x {found[1]}.")
            self.create_btn.setEnabled(False)
            return
        if sheet:
            if self._sheet_image is None:
                self.summary.setText("No sprite sheet selected")
                self.create_btn.setEnabled(False)
                return
            if self._grid.error:
                self.summary.setStyleSheet(ORANGE)
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

    def _set_size_radio(self, typed: bool) -> None:
        """Choose 'Set frame size' (typed) or 'Set from imported sprites' without triggering a refresh."""
        self.size_group.blockSignals(True)
        (self.size_radio if typed else self.from_files).setChecked(True)
        self.size_group.blockSignals(False)

    def _native_size(self) -> tuple[int, int] | None:
        """The size of the imported sprites: the sprite sheet's boxes, or the one size shared by every file."""
        if self.sheet_mode():
            return (self._grid.width, self._grid.height) if self._sheet_image is not None and not self._grid.error else None
        return self._found_size()

    # ---- actions ------------------------------------------------------------------------
    def _browse(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(
            self, "Select image files", self._folder, "Images (*.png *.bmp *.gif)")
        if names:
            self._folder = str(Path(names[0]).parent)
            self.set_files([Path(n) for n in names])

    def sheet_mode(self) -> bool:
        return self.sheet_radio.isChecked()

    def blank_mode(self) -> bool:
        return self.blank_radio.isChecked()

    def _blank_folder_taken(self) -> bool:
        """A blank project needs a new name: no project folder with that name may exist yet."""
        name = self.name.text()
        return valid_project_name(name) and paths.project_folder(paths.projects_folder(), name).exists()

    def _mode_changed(self) -> None:
        """Only one of the two ways to bring sprites in is active; the other one is cleared and greyed out."""
        if self.sheet_mode():
            self._files, self._sizes = [], []
            self.file_list.clear()
            self._set_size_radio(False)
        elif self.blank_mode():
            self._files, self._sizes = [], []
            self._clear_sheet()
            self.file_list.clear()
            self._set_size_radio(True)
        else:
            self._clear_sheet()
            self._sizes = []
            self.file_list.clear()
            self._set_size_radio(False)
        self._refresh()

    def _clear_sheet(self) -> None:
        self.sheet_name.clear()
        self.frame_name.clear()
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
        self.sheet_radio.setChecked(True)
        self._files, self._sizes = [], []
        self._sheet_path = Path(path)
        self.sheet_name.setText(self._sheet_path.name)
        self.sheet_name.setCursorPosition(0)
        self.frame_name.setText(clean_name(self._sheet_path.stem)[:NAME_MAX - 4])
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

    def _larger_canvas(self, native: tuple[int, int] | None) -> tuple[int, int] | None:
        """The typed canvas size when it is larger than the imported sprites (they are then centred on it), else None.
        A canvas smaller than the sprites never gets here: Create Project stays disabled."""
        if self.from_files.isChecked() or native is None:
            return None
        canvas = (self.width_box.value(), self.height_box.value())
        return canvas if canvas != native and canvas[0] >= native[0] and canvas[1] >= native[1] else None

    @staticmethod
    def _centre_on_canvas(result: ImportResult, canvas: tuple[int, int]) -> None:
        """Put every frame in the middle of a bigger canvas, filled with the transparent colour. An odd leftover
        pixel goes to the right and the bottom."""
        fill = result.transparent_default
        for f in result.frames:
            big = Image.new("RGB", canvas, fill)
            big.paste(f.image, ((canvas[0] - f.image.width) // 2, (canvas[1] - f.image.height) // 2))
            f.image = big

    def _create_from_sheet(self) -> None:
        g = self._grid
        if self.box_colour.colour == self.fill_colour.colour:
            messages.warn(self, "The box colour and the transparent colour must be different.")
            return
        system = self.selected_system()
        frame_name = self.frame_name.text()
        if not valid_name(frame_name, NAME_MAX - 4):
            messages.warn(self, "The frame name can only use letters, numbers, - and _ (no spaces), "
                                f"up to {NAME_MAX - 4} characters.")
            return
        result = sheet_import.import_sheet(self._sheet_image, frame_name, g,
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
            messages.adjusted(self, [f"Colours in this sprite sheet were adjusted to the nearest colour valid for "
                                     f"{system.name}."], "")
        size = (g.width, g.height)
        canvas = self._larger_canvas(size)
        if canvas:
            self._centre_on_canvas(result, canvas)
            size = canvas
        self.project = create_project(self.name.text(), system, size[0], size[1], result, self.fps.currentData())
        self.project.transparent = system.snap(self.fill_colour.colour)
        self.project.source_sheet = str(self._sheet_path)
        self.accept()

    def _create_blank(self) -> None:
        if self._blank_folder_taken():
            messages.warn(self, f"A project called {self.name.text()} already exists. Choose another name.")
            return
        system = self.selected_system()
        w, h = self.width_box.value(), self.height_box.value()
        transparent = system.default_transparent if system.is_fixed else snap_colour((255, 0, 255), system.bits)
        result = ImportResult(frames=[ImportedFrame("Frame", Image.new("RGB", (w, h), transparent))
                                      for n in range(1, self.blank_frames.value() + 1)])
        self.project = create_project(self.name.text(), system, w, h, result, self.fps.currentData())
        self.project.transparent = transparent
        self.accept()

    def _create(self) -> None:
        if self.blank_mode():
            self._create_blank()
            return
        if self.sheet_mode():
            self._create_from_sheet()
            return
        size = self._frame_size()
        if size is None:
            return
        w, h = size
        system = self.selected_system()
        canvas = self._larger_canvas(self._found_size())
        if canvas:
            w, h = self._found_size()                         # the files are read at their own size, then centred
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
            messages.adjusted(self, [f"Colours in these image files were adjusted to the nearest colour valid for "
                                     f"{system.name}."], "")

        if canvas:
            self._centre_on_canvas(result, canvas)
            w, h = canvas
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
        except InvalidNameError:
            messages.warn(self, f"{Path(path).name} {InvalidNameError.MESSAGE}")
            return
        except ProjectFileError:
            messages.warn(self, f"{path.name} could not be opened. It may be damaged or saved by a "
                                "different version of RunSpriteRun.")
            return
        self.accept()
