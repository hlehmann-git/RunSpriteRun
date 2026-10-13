"""Starting and leaving Edit mode, with the two questions the owner is asked (V2.0)."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QLabel, QRadioButton, QVBoxLayout, QWidget)

from src.app import messages
from src.core.edit import EditError

MSG_LEAVE_FIRST = "Switch back to RunSpriteRun mode first."
MSG_LEAVE_DETAIL = "Your edits are not applied to the frame until you leave Edit mode."


class EditStartDialog(QDialog):
    """Create new frame or edit the existing one; a new frame goes before or after the selected frame, or first."""

    def __init__(self, parent: QWidget, selected_number: int) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit mode")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("What do you want to edit?"))
        self.existing = QRadioButton(f"Edit existing frame (frame {selected_number})")
        self.new = QRadioButton("Create new frame")
        self.existing.setChecked(True)
        lay.addWidget(self.existing)
        lay.addWidget(self.new)
        self.before = QRadioButton(f"Insert before the selected frame ({selected_number})")
        self.after = QRadioButton(f"Insert after the selected frame ({selected_number})")
        self.first = QRadioButton("Insert as Frame 1")
        self.after.setChecked(True)
        self.copy = QCheckBox("Start from a copy of the selected frame")
        for w in (self.before, self.after, self.first, self.copy):
            w.setStyleSheet("margin-left: 22px;")
            lay.addWidget(w)
        self.new.toggled.connect(self._sync)
        self._sync()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _sync(self) -> None:
        for w in (self.before, self.after, self.first, self.copy):
            w.setEnabled(self.new.isChecked())

    def choice(self) -> dict:
        where = "before" if self.before.isChecked() else "first" if self.first.isChecked() else "after"
        return {"new": self.new.isChecked(), "where": where, "copy": self.copy.isChecked()}


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
