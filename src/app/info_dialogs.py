"""Project Information (FR-3.14), Help and About boxes (File and Help menus, section 5.3)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from src.core.project import Project
from src.core.rules import GAP_MAX, GAP_MIN

APP_NAME = "RunSpriteRun"
AUTHOR = "Harley Lehmann"
VERSION = "1.0"
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
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("About RunSpriteRun")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(440)
        title = QLabel(APP_NAME)
        f = QFont(title.font())
        f.setPointSizeF(f.pointSizeF() * 1.9)
        f.setBold(True)
        title.setFont(f)
        self.author = QLabel(f"by {AUTHOR}")
        self.version = QLabel(f"Version {VERSION}")
        self.version.setStyleSheet("color: #8a8a94;")
        self.text = QPlainTextEdit("\n".join(PLACEHOLDER[:5]))     # how the app was made (placeholder)
        self.text.setReadOnly(True)
        self.text.setFixedHeight(5 * self.text.fontMetrics().lineSpacing() + 20)
        ok = QPushButton("OK")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(ok)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(self.author)
        layout.addWidget(self.version)
        layout.addSpacing(8)
        layout.addWidget(self.text)
        layout.addSpacing(8)
        layout.addLayout(buttons)
