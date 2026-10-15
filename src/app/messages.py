"""Message boxes in one place so the rest of the app (and the tests) can call them simply.
Wording follows the PRD message table (section 5.5)."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def info(parent: QWidget, text: str, detail: str | None = None) -> None:
    box = QMessageBox(QMessageBox.Information, "RunSpriteRun", text, QMessageBox.Ok, parent)
    if detail:
        box.setInformativeText(detail)
    box.exec()


def warn(parent: QWidget, text: str, detail: str | None = None) -> None:
    box = QMessageBox(QMessageBox.Warning, "RunSpriteRun", text, QMessageBox.Ok, parent)
    if detail:
        box.setInformativeText(detail)
    box.exec()


def choose(parent: QWidget, text: str, detail: str, yes_text: str, no_text: str) -> bool:
    """Two-button question. Returns True for the first (yes) button."""
    box = QMessageBox(QMessageBox.Question, "RunSpriteRun", text, QMessageBox.NoButton, parent)
    box.setInformativeText(detail)
    yes = box.addButton(yes_text, QMessageBox.AcceptRole)
    box.addButton(no_text, QMessageBox.RejectRole)
    box.exec()
    return box.clickedButton() is yes


def overlap(parent: QWidget, text: str) -> bool:
    """Group overlap message with a Copy into new group button to the left of OK. True if Copy was clicked."""
    box = QMessageBox(QMessageBox.Warning, "RunSpriteRun", text, QMessageBox.NoButton, parent)
    copy = box.addButton("Copy into new group", QMessageBox.AcceptRole)
    ok = box.addButton("OK", QMessageBox.AcceptRole)
    box.setDefaultButton(ok)
    box.setEscapeButton(ok)
    box.exec()
    return box.clickedButton() is copy


def adjusted(parent: QWidget, lines: list[str], details: str) -> None:
    """FR-1.2 check 4 warning with a Details button listing original and adjusted values."""
    box = QMessageBox(QMessageBox.Warning, "RunSpriteRun", "\n".join(lines), QMessageBox.Ok, parent)
    if details:
        box.setDetailedText(details)
    box.exec()


def save_changes(parent: QWidget, name: str) -> str:
    """FR-4.4: "Save changes to <project> before closing?" Returns "save", "discard" or "cancel"."""
    box = QMessageBox(QMessageBox.Question, "RunSpriteRun", f"Save changes to {name} before closing?",
                      QMessageBox.NoButton, parent)
    save = box.addButton("Save", QMessageBox.AcceptRole)
    discard = box.addButton("Don't Save", QMessageBox.DestructiveRole)
    box.addButton("Cancel", QMessageBox.RejectRole)
    box.exec()
    return "save" if box.clickedButton() is save else "discard" if box.clickedButton() is discard else "cancel"


def apply_edit(parent: QWidget) -> str:
    """Leaving Edit mode with edits: "apply" (flatten and save them to the frame), "discard" or "keep" (editing)."""
    box = QMessageBox(QMessageBox.Question, "RunSpriteRun", "Do you want to flatten and save your changes?",
                      QMessageBox.NoButton, parent)
    box.setInformativeText("Apply puts the edits on the frame (the layers are kept). Discard throws them away, "
                           "including a new frame.")
    apply = box.addButton("Apply changes", QMessageBox.AcceptRole)
    discard = box.addButton("Discard changes", QMessageBox.DestructiveRole)
    box.addButton("Keep editing", QMessageBox.RejectRole)
    box.setDefaultButton(apply)
    box.exec()
    return "apply" if box.clickedButton() is apply else "discard" if box.clickedButton() is discard else "keep"
