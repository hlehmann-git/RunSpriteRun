"""Starting and leaving Edit mode, with the two questions the owner is asked (V2.0)."""
from __future__ import annotations

from PySide6.QtWidgets import (QButtonGroup, QDialog, QDialogButtonBox, QLabel, QRadioButton, QVBoxLayout, QWidget)

from src.app import messages
from src.core.edit import EditError

MSG_LEAVE_FIRST = "Switch back to RunSpriteRun mode first."
MSG_LEAVE_DETAIL = "Your edits are not applied to the frame until you leave Edit mode."


class EditStartDialog(QDialog):
    """Edit the existing frame, or create a new one: empty or a copy of the selected frame, placed before or after the
    selected frame, or as frame 1."""

    def __init__(self, parent: QWidget, selected_number: int) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit mode")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("What do you want to edit?"))
        self.existing = QRadioButton(f"Edit existing frame (frame {selected_number})")
        self.new = QRadioButton("Create new frame")
        self.existing.setChecked(True)
        top = QButtonGroup(self)                         # the two main choices: one group, so they never undo each other
        top.addButton(self.existing)
        top.addButton(self.new)
        lay.addWidget(self.existing)
        lay.addWidget(self.new)
        # the six ways to create a frame: where it goes x what it starts from, all in their own radio group
        self.copy_before = QRadioButton(f"Use existing frame and insert before current frame ({selected_number})")
        self.copy_after = QRadioButton(f"Use existing frame and insert after current frame ({selected_number})")
        self.copy_first = QRadioButton("Use existing frame and insert as frame 1")
        self.empty_before = QRadioButton(f"Empty Frame and insert before current frame ({selected_number})")
        self.empty_after = QRadioButton(f"Empty Frame and insert after current frame ({selected_number})")
        self.empty_first = QRadioButton("Empty Frame and insert as frame 1")
        self.options = (self.copy_before, self.copy_after, self.copy_first,
                        self.empty_before, self.empty_after, self.empty_first)
        sub = QButtonGroup(self)
        for w in self.options:
            sub.addButton(w)
            w.setStyleSheet("margin-left: 22px;")
            lay.addWidget(w)
        self.empty_after.setChecked(True)
        self._groups = (top, sub)
        self.new.toggled.connect(self._sync)
        self._sync()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _sync(self) -> None:
        for w in self.options:
            w.setEnabled(self.new.isChecked())

    def choice(self) -> dict:
        where = ("before" if self.copy_before.isChecked() or self.empty_before.isChecked()
                 else "first" if self.copy_first.isChecked() or self.empty_first.isChecked() else "after")
        copy = self.copy_before.isChecked() or self.copy_after.isChecked() or self.copy_first.isChecked()
        return {"new": self.new.isChecked(), "where": where, "copy": copy}


def enter(parent: QWidget, session) -> bool:
    """Ask what to edit, then start Edit mode. Returns True if Edit mode is on."""
    c = session.controller
    if session.mode or c.project is None or not c.project.frames:
        return session.mode
    dialog = EditStartDialog(parent, c.selected + 1)
    if dialog.exec() != QDialog.Accepted:
        return False
    try:
        return session.begin(**dialog.choice())
    except EditError as e:
        messages.warn(parent, str(e))
        return False


def leave(parent: QWidget, session) -> bool:
    """Leave Edit mode: Apply, Discard or Keep editing. Returns True if Edit mode is now off."""
    if not session.mode:
        return True
    if not session.has_changes():
        session.finish(False)
        return True
    answer = messages.apply_edit(parent)
    if answer == "keep":
        return False
    session.finish(answer == "apply")
    return True
