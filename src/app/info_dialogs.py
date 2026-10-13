"""Project Information (FR-3.14), Help and About boxes (File and Help menus, section 5.3)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from src.core.project import Project
from src.core.rules import GAP_MAX, GAP_MIN

APP_NAME = "RunSpriteRun"
AUTHOR = "Harley Lehmann"
VERSION = "2.0.1"
CLAUDE_COMMENTS = 5649      # a nice touch from the owner, never updated
BRAND_IMAGE = Path(__file__).parent / "assets" / "brand.png"
ABOUT_DESCRIPTION = [
    "RunSpriteRun is a windows app that takes the 2026 out of 1992 when it comes to frame grouping, animations, "
    "editing and saving. Think Deluxe Paint for the Amiga but stripped down to what you want and need.",
    "Work in the system you want.  It's all you."]
ABOUT_SMALL_PRINT = ["Made by Harley Lehmann with my Buddy Claude.", "Built with Python, PySide6 and Pillow."]
PLACEHOLDER = ["Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
               "Sed do eiusmod tempor incididunt ut labore et dolore.",
               "Ut enim ad minim veniam, quis nostrud exercitation.",
               "Duis aute irure dolor in reprehenderit in voluptate.",
               "Excepteur sint occaecat cupidatat non proident.",
               "Sunt in culpa qui officia deserunt mollit anim id est laborum.",
               "Curabitur pretium tincidunt lacus, nulla gravida orci a odio.",
               "Nullam varius, turpis et commodo pharetra, est eros bibendum elit.",
               "Integer ac sem ut nibh dapibus tristique.",
               "Vestibulum ante ipsum primis in faucibus orci luctus."]


def information_rows(p: Project) -> list[tuple[str, str]]:
    """The details shown in Project Information, in the order of FR-3.14."""
    s = p.system
    return [
        ("Project name", p.name),
        ("File location", p.file_path or "Not saved yet"),
        ("Target system", s.name),
        ("Max sprite colours", str(s.max_colours)),
        ("Bits per channel", f"{s.bits} bits, RGB {s.bits}:{s.bits}:{s.bits}"),
        ("Colour depth", f"{s.bits * 3}-bit"),
        ("Total palette colours", f"{s.total_colours:,}"),
        ("Frame size", f"{p.width} x {p.height}"),
        ("Frames", str(len(p.frames))),
        ("Frame Groups", str(len(p.groups))),
        ("Frames per second", str(p.fps)),
        ("Colours in use", f"{p.colours_in_use()} / {s.max_colours}"),
    ]


def _bold(label: QLabel) -> QLabel:
    f = QFont(label.font())
    f.setBold(True)
    label.setFont(f)
    return label


class ProjectInformationDialog(QDialog):
    def __init__(self, parent: QWidget, project: Project, controller=None) -> None:
        super().__init__(parent)
        self.project = project
        self.controller = controller
        self.setWindowTitle("Project Information")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(480)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)
        for row, (label, value) in enumerate(information_rows(project)):
            grid.addWidget(_bold(QLabel(label)), row, 0, Qt.AlignTop)
            v = QLabel(value)
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(v, row, 1)
        row = len(information_rows(project))
        grid.addWidget(_bold(QLabel("Sprite sheet gap")), row, 0, Qt.AlignVCenter)
        self.gap_box = QSpinBox()                      # the one editable detail (FR-3.14)
        self.gap_box.setRange(GAP_MIN, GAP_MAX)
        self.gap_box.setValue(project.gap)
        gap_row = QHBoxLayout()
        gap_row.addWidget(self.gap_box)
        gap_row.addWidget(QLabel("pixels (0-16), used when saving"))
        gap_row.addStretch()
        grid.addLayout(gap_row, row, 1)
        grid.setColumnStretch(1, 1)
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(close)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(16)
        layout.addLayout(grid)
        layout.addLayout(buttons)


    def accept(self) -> None:
        if self.controller is not None:
            self.controller.set_gap(self.gap_box.value())
        super().accept()


class HelpDialog(QDialog):
    """Ten lines of placeholder text for the owner to replace (Help menu)."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("RunSpriteRun Help")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(480)
        self.text = QPlainTextEdit("\n".join(PLACEHOLDER))
        self.text.setReadOnly(True)
        self.text.setFixedHeight(10 * self.text.fontMetrics().lineSpacing() + 20)
        ok = QPushButton("OK")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(ok)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(16)
        layout.addWidget(self.text)
        layout.addLayout(buttons)


class AboutDialog(QDialog):
    """Branding image, version, comment count, description and small print (Help > About)."""

    IMAGE_WIDTH = 480

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("About RunSpriteRun")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.picture = QLabel()
        self.picture.setAlignment(Qt.AlignCenter)
        pix = QPixmap(str(BRAND_IMAGE))
        if not pix.isNull():
            scaled = pix.scaledToWidth(self.IMAGE_WIDTH, Qt.FastTransformation)       # crisp pixels
            self.picture.setPixmap(scaled)
            self.picture.setFixedSize(scaled.size())                                 # never squeezed or cropped
        self.version = _bold(QLabel(f"Version {VERSION}"))
        self.author = _bold(QLabel("by Harley Lehmann"))
        dot = _bold(QLabel("\u00b7"))
        self.comments = QLabel(f"Number of Claude comments from Harley: {CLAUDE_COMMENTS} (from the start)")
        self.comments.setStyleSheet("color: #78c8ff;")
        self.description_title = _bold(QLabel("Description"))
        self.description = QLabel("\n\n".join(ABOUT_DESCRIPTION))
        self.description.setWordWrap(True)
        self.description.setFixedWidth(self.IMAGE_WIDTH)                            # wraps at the image width
        self.small_print_title = _bold(QLabel("Small Print"))
        self.small_print = QLabel("\n".join(ABOUT_SMALL_PRINT))
        self.small_print.setStyleSheet("color: #8a8a94;")
        ok = QPushButton("OK")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(ok)
        head = QHBoxLayout()
        head.addWidget(self.version)
        head.addWidget(dot)
        head.addWidget(self.author)
        head.addStretch()
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QVBoxLayout.SetFixedSize)                           # the box is exactly as tall as its content
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(8)
        layout.addWidget(self.picture, 0, Qt.AlignHCenter)
        layout.addSpacing(4)
        layout.addLayout(head)
        layout.addWidget(self.comments)
        layout.addSpacing(8)
        layout.addWidget(self.description_title)
        layout.addWidget(self.description)
        layout.addSpacing(8)
        layout.addWidget(self.small_print_title)
        layout.addWidget(self.small_print)
        layout.addSpacing(8)
        layout.addLayout(buttons)
