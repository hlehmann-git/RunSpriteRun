"""Group > Start State (FR-3.10, FR-3.11): what RunSpriteRun shows from F5 until the first key press."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.app.rule_editor import RuleEditor
from src.core.project import Project, Rule


class StartStateDialog(QDialog):
    def __init__(self, parent: QWidget, project: Project) -> None:
        super().__init__(parent)
        self.setWindowTitle("Start State")
        self.setModal(True)
        self.project = project
        root = QVBoxLayout(self)
        hint = QLabel("Shown from F5 until the first key press.")
        hint.setStyleSheet("color: #9aa0ae;")
        root.addWidget(hint)
        self.editor = RuleEditor(self)
        root.addWidget(self.editor)
        # Never set: the start state is Go To Frame 1 of the timeline (FR-3.10).
        current = project.start_state or Rule("frame", project.frames[0].label)
        self.editor.load(project, current)
        row = QHBoxLayout()
        row.addStretch(1)
        self.ok = QPushButton("OK")
        self.ok.setDefault(True)
        cancel = QPushButton("Cancel")
        row.addWidget(self.ok)
        row.addWidget(cancel)
        root.addLayout(row)
        self.ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        self.setFixedSize(self.sizeHint().width() + 40, self.sizeHint().height())

    def rule(self) -> Rule | None:
        return self.editor.rule()
