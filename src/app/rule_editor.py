"""The 'Go To Frame / Go to Group + Loop' choice used by On Release (FR-3.11) and by the Start State dialog."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QComboBox, QRadioButton, QWidget

from src.app.theme import short_popup
from src.app.common import frame_choice_text
from src.core.project import Project, Rule


class RuleEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(238, 72)
        self.radio_frame = QRadioButton("Go To Frame", self)
        self.radio_group = QRadioButton("Go to Group", self)
        self.radio_frame.move(0, 0)
        self.radio_group.move(0, 40)
        self.buttons = QButtonGroup(self)
        self.buttons.addButton(self.radio_frame)
        self.buttons.addButton(self.radio_group)
        self.frame_combo = QComboBox(self)
        self.frame_combo.setGeometry(101, 0, 124, 26)
        self.group_combo = QComboBox(self)
        short_popup(self.frame_combo)
        short_popup(self.group_combo)
        self.group_combo.setGeometry(98, 38, 80, 26)
        self.loop = QCheckBox("Loop", self)
        self.loop.move(184, 41)
        for w in (self.radio_frame, self.radio_group, self.loop):
            w.toggled.connect(self._changed)
        for c in (self.frame_combo, self.group_combo):
            c.currentIndexChanged.connect(self._changed)

    def compact(self) -> None:
        """The wider-row layout used inside the Set Frame Group panel (the Start State dialog keeps the default)."""
        self.setFixedSize(232, 54)
        self.radio_frame.setGeometry(0, 0, 100, 26)
        self.frame_combo.setGeometry(104, 0, 118, 26)
        self.radio_group.setGeometry(0, 28, 100, 26)
        self.group_combo.setGeometry(104, 28, 66, 26)
        self.loop.setGeometry(178, 28, 60, 26)

    def _changed(self) -> None:
        self.loop.setEnabled(self.radio_group.isChecked())     # Loop only goes with Go to Group
        self.changed.emit()

    def load(self, project: Project, rule: Rule | None) -> None:
        """Fill the lists from the project and show `rule` (None shows neither choice)."""
        self.blockSignals(True)
        for w in (self.radio_frame, self.radio_group, self.loop, self.frame_combo, self.group_combo):
            w.blockSignals(True)
        self.frame_combo.clear()
        for i, f in enumerate(project.frames):
            self.frame_combo.addItem(frame_choice_text(i, f.label), f.label)
        self.group_combo.clear()
        for g in project.groups:
            self.group_combo.addItem(g.name, g.name)
        self.radio_group.setEnabled(self.group_combo.count() > 0)
        self.buttons.setExclusive(False)
        self.radio_frame.setChecked(False)
        self.radio_group.setChecked(False)
        self.buttons.setExclusive(True)
        self.loop.setChecked(False)
        if rule is not None and rule.kind == "frame":
            self.radio_frame.setChecked(True)
            self.frame_combo.setCurrentIndex(max(0, self.frame_combo.findData(rule.target)))
        elif rule is not None and rule.kind == "group":
            self.radio_group.setChecked(True)
            self.group_combo.setCurrentIndex(max(0, self.group_combo.findData(rule.target)))
            self.loop.setChecked(rule.loop)
        for w in (self.radio_frame, self.radio_group, self.loop, self.frame_combo, self.group_combo):
            w.blockSignals(False)
        self.blockSignals(False)
        self.loop.setEnabled(self.radio_group.isChecked())

    def rule(self) -> Rule | None:
        if self.radio_frame.isChecked() and self.frame_combo.count():
            return Rule("frame", self.frame_combo.currentData())
        if self.radio_group.isChecked() and self.group_combo.count():
            return Rule("group", self.group_combo.currentData(), self.loop.isChecked())
        return None
