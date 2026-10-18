"""Ctrl+V in the Timeline: before or after the frame that was copied?"""
from PySide6.QtWidgets import QButtonGroup, QDialog, QDialogButtonBox, QLabel, QRadioButton, QVBoxLayout


class PasteFrameDialog(QDialog):
    def __init__(self, parent, copied_number: int, copied_label: str, count: int = 1, last_number: int | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Paste frame" if count == 1 else "Paste frames")
        lay = QVBoxLayout(self)
        if count == 1:
            lay.addWidget(QLabel(f"Paste a copy of {copied_label}:"))
            self.before = QRadioButton(f"Before the copied frame ({copied_number})")
            self.after = QRadioButton(f"After the copied frame ({copied_number})")
        else:
            lay.addWidget(QLabel(f"Paste a copy of the {count} copied frames:"))
            self.before = QRadioButton(f"Before the first copied frame ({copied_number})")
            self.after = QRadioButton(f"After the last copied frame ({last_number})")
        self.after.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.before)
        group.addButton(self.after)
        self._group = group
        lay.addWidget(self.before)
        lay.addWidget(self.after)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def paste_after(self) -> bool:
        return self.after.isChecked()
