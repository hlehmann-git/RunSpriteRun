"""Frame Group Preview (FR-3.3): shows the selected frame and plays its group when Play is clicked.
Nothing plays by itself. It has no pixel grid and ignores keys and resting states."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QWidget

from src.app.theme import short_popup
from src.app.arrow_button import ArrowButton
from src.app.controller import Controller
from src.app.panel import Panel
from src.app.theme import TOGGLE_BUTTON_STYLE
from src.app.sprite_view import SpriteView, offer_to_picker
from src.core import edit


def caption_text(name: str, first: int, last: int) -> str:
    """For example 'Right · F03–F06' (frame numbers are 1-based)."""
    return f"{name} · F{first + 1:02d}–F{last + 1:02d}"


class GroupPreviewPanel(Panel):
    def __init__(self, parent: QWidget, controller: Controller) -> None:
        super().__init__("Frame Group Preview", parent)
        self.controller = controller
        self.chooser = QComboBox(self)
        self.chooser.setGeometry(179, 8, 96, 26)
        short_popup(self.chooser)
        self.view = SpriteView(self, grid=False)
        self.view.move(16, 38)
        offer_to_picker(self.view, controller)            # the colour picker can take a colour from here
        self.play_btn = QPushButton("Play", self)
        self.play_btn.setCheckable(True)                 # one on / off button: lit while the group is playing
        self.play_btn.setFocusPolicy(Qt.NoFocus)
        self.play_btn.setStyleSheet(TOGGLE_BUTTON_STYLE)
        self.play_btn.setGeometry(16, 299, 50, 22)
        self.back_btn = ArrowButton("left", self, "Previous frame in this group")
        self.fwd_btn = ArrowButton("right", self, "Next frame in this group")
        self.back_btn.move(74, 299)
        self.fwd_btn.move(102, 299)
        self.caption = QLabel("", self)
        self.caption.setStyleSheet("color: #9aa0ae;")
        self.caption.move(136, 301)
        self._shown = -1                                 # the frame this view shows now
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._frames: list[int] = []
        self._pos = 0
        self._playing_key: tuple | None = None       # (name, first, last, fps) of what is playing

        self.chooser.activated.connect(lambda _i: self._chosen())
        self.play_btn.clicked.connect(lambda on: self.play() if on else self.stop())
        self.back_btn.clicked.connect(lambda: self.step(-1))
        self.fwd_btn.clicked.connect(lambda: self.step(1))
        controller.project_changed.connect(self._project_changed)
        controller.frames_changed.connect(self.refresh)
        controller.selection_changed.connect(self._selection_changed)

    # ---- model -> widgets -----------------------------------------------------------------------
    def _project_changed(self) -> None:
        self.stop()
        self.chooser.clear()
        self._playing_key = None
        self.view.set_sprite(None)
        self.refresh()

    def refresh(self) -> None:
        """The groups or frames changed: update the list; anything that was playing and changed stops."""
        p = self.controller.project
        names = [g.name for g in p.groups] if p else []
        keep = self.chooser.currentText()
        self.chooser.blockSignals(True)
        self.chooser.clear()
        self.chooser.addItems(names)
        self.chooser.setCurrentIndex(names.index(keep) if keep in names else -1)
        self.chooser.blockSignals(False)
        g = self._group()
        if self.timer.isActive() and (g is None or self._playing_key != (g.name, g.first, g.last, p.fps)):
            self.stop()
        self._update_controls()
        if not self.timer.isActive() and p is not None and p.frames:
            self._show_frame(self._current_frame())

    def _current_frame(self) -> int:
        """The frame shown while nothing plays: the selected frame."""
        return self.controller.selected

    def _selection_changed(self, index: int) -> None:
        """Selecting a frame shows it here (and its group's name), and stops any playing. It never starts playing."""
        p = self.controller.project
        if p is None or not 0 <= index < len(p.frames):
            return
        self.stop()
        name = edit.group_of_frame(p)[index]
        self.chooser.blockSignals(True)
        self.chooser.setCurrentIndex(self.chooser.findText(name) if name else -1)
        self.chooser.blockSignals(False)
        self._update_controls()
        self._show_frame(index)

    def _chosen(self) -> None:
        """A group picked in the drop-down: its first frame is shown; it plays only when Play is clicked."""
        self.stop()
        g = self._group()
        self._update_controls()
        if g is not None:
            self._show_frame(g.first)

    def _group(self):
        p = self.controller.project
        if p is None:
            return None
        return next((g for g in p.groups if g.name == self.chooser.currentText()), None)

    def _update_controls(self) -> None:
        g = self._group()
        self.play_btn.setEnabled(g is not None)
        self.back_btn.setEnabled(g is not None)
        self.fwd_btn.setEnabled(g is not None)
        self.caption.setText(caption_text(g.name, g.first, g.last) if g else "")
        self.caption.adjustSize()

    def _show_frame(self, index: int) -> None:
        p = self.controller.project
        self._shown = index
        if p is None or not 0 <= index < len(p.frames):
            self.view.set_sprite(None)
            return
        self.view.set_sprite(p.frames[index].image, p.transparent)

    # ---- playback -------------------------------------------------------------------------------
    def play(self) -> None:
        """Play: the chosen group from its first frame to its last, repeating until Stop."""
        p = self.controller.project
        g = self._group()
        if p is None or g is None:
            return
        self._frames = list(range(g.first, g.last + 1))
        self._pos = 0
        self._playing_key = (g.name, g.first, g.last, p.fps)
        self.timer.start(round(1000 / p.fps))
        self.play_btn.setChecked(True)
        self._show()

    def step(self, delta: int) -> None:
        """Show the previous / next frame of the chosen group, wrapping round at the ends. A playing group is
        paused first and the step starts from the frame being shown. Only this view changes: the selected frame
        stays as it was."""
        p = self.controller.project
        g = self._group()
        if p is None or g is None:
            return
        self.timer.stop()
        self.play_btn.setChecked(False)
        n = g.last - g.first + 1
        cur = self._shown if g.first <= self._shown <= g.last else g.first
        index = g.first + (cur - g.first + delta) % n
        self._show_frame(index)
        self.controller.playing_frame.emit(index)

    def _show(self) -> None:
        index = self._frames[self._pos]
        self._show_frame(index)
        self.controller.playing_frame.emit(index)

    def _tick(self) -> None:
        self._pos = (self._pos + 1) % len(self._frames)
        self._show()

    def stop(self) -> None:
        """Stop, leaving the current frame shown."""
        self.timer.stop()
        self.play_btn.setChecked(False)
        self.controller.playing_frame.emit(-1)
