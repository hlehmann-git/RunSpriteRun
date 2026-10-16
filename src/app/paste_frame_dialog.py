"""Ctrl+V in the Timeline: before or after the selected frame?"""
from PySide6.QtWidgets import QButtonGroup, QDialog, QDialogButtonBox, QLabel, QRadioButton, QVBoxLayout


class PasteFrameDialog(QDialog):
    def __init__(self, parent, selected_number: int, copied_label: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Paste frame")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Paste a copy of {copied_label}:"))
        self.before = QRadioButton(f"Before the selected frame ({selected_number})")
        self.after = QRadioButton(f"After the selected frame ({selected_number})")
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
