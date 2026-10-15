"""Holds the open project and the selected frame, and tells the panels when something changed.
Panels only display this state and pass user actions here (section 6.1)."""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QWidget

from src.core.colour import snap_colour
from src.app import messages
from src.app.edit_session import EditSession
from src.core import edit, groups, history, palette
from src.core.project import Rule
from src.core.project import Project
from src.core.runner import Runner
from src.io import settings as settings_io


class Controller(QObject):
    project_changed = Signal()        # a different project is open (or none)
    selection_changed = Signal(int)   # the selected frame (0-based)
    frames_changed = Signal()         # frame order, labels or groups changed
    playing_frame = Signal(int)       # frame being shown by a playing view, or -1 when none is playing
    run_frame = Signal(int)           # frame the RunSpriteRun window shows (always: the start state when stopped)
    run_state = Signal(bool)          # F5: RunSpriteRun started or stopped
    keys_held = Signal(list)          # assigned keys now held, for the Keys panel
    settings_changed = Signal()       # Settings were changed (OK in the Settings dialog)
    history_changed = Signal()        # undo / redo became available or unavailable
    palette_clicked = Signal(int)     # a palette square was clicked (0-based slot)
    frame_pixel_clicked = Signal(tuple)  # a pixel of the Frame view was clicked: its colour
    palette_right_clicked = Signal(int)  # right click on a palette square (0-based slot)
    frame_pixel_right_clicked = Signal(tuple)  # right click on a pixel of the Frame view: its colour

    def __init__(self, parent_widget: QWidget | None = None, settings: settings_io.Settings | None = None) -> None:
        super().__init__()
        self.settings = settings if settings is not None else settings_io.load()
        self.project: Project | None = None
        self.selected = 0
        self.parent_widget = parent_widget
        self.runner: Runner | None = None
        self.history = history.History()
        self.edit = EditSession(self)
        self.eyedropper_armed = False      # set by the Colour editor
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.frames_changed.connect(self._frames_changed)
        self.selection_changed.connect(self._selection_changed)

    def set_project(self, project: Project | None) -> None:
        self.stop_run()
        self.edit.reset()
        self.project = project
        self.history.clear()
        self.history_changed.emit()
        self.runner = Runner(project) if project is not None else None
        self.selected = 0
        self.project_changed.emit()
        self.run_frame.emit(-1)
        if project is not None:
            self.selection_changed.emit(0)

    def select(self, index: int) -> None:
        if self.project is None or not self.project.frames:
            return
        index = max(0, min(index, len(self.project.frames) - 1))
        if index != self.selected and self.edit.mode and self.edit.floating is not None:
            self.edit.notice.emit("Press Enter to fix the paste or Esc to discard it before changing frame.")
            self.selection_changed.emit(self.selected)           # the drop-downs and timeline fall back
            return
        if index != self.selected:
            self.selected = index
        self.selection_changed.emit(index)

    def rename(self, index: int, text: str) -> bool:
        """Returns True if the label was accepted (or unchanged). A refused label shows its message."""
        assert self.project is not None
        if self.edit.mode:
            return False
        try:
            before = self.checkpoint()
            if edit.rename_label(self.project, index, text):
                self.commit(before)
                self.frames_changed.emit()
            return True
        except edit.EditError as e:
            messages.warn(self.parent_widget, str(e))
            return False

    def move_frame(self, src: int, dst: int) -> bool:
        assert self.project is not None
        if self.edit.mode:
            return False

        def confirm(names: list[str]) -> bool:
            who = ", ".join(names)
            return messages.choose(self.parent_widget, f"Group {who} has no frames left and will be deleted.",
                                   "", "Delete", "Cancel")
        before = self.checkpoint()
        if not edit.move_frame(self.project, src, dst, confirm):
            return False
        self.commit(before)
        self.selected = dst                       # the selection follows the moved frame
        self.frames_changed.emit()
        self.selection_changed.emit(dst)
        return True

    def move_selected(self, delta: int) -> bool:
        """Ctrl+Left / Ctrl+Right: move the selected frame one place."""
        if self.project is None:
            return False
        dst = self.selected + delta
        if not 0 <= dst < len(self.project.frames):
            return False
        return self.move_frame(self.selected, dst)

    # ---- groups -------------------------------------------------------------------------------
    def delete_group(self, name: str) -> list[str]:
        """Delete a group (the caller has already asked). Returns the rules that were reset."""
        assert self.project is not None
        affected = groups.rules_pointing_to(self.project, name)
        before = self.checkpoint()
        edit.delete_group(self.project, name)
        self.commit(before)
        self.frames_changed.emit()
        return affected

    def copy_into_new_group(self, name: str, first: int, last: int, key, on_release, colour) -> bool:
        """Set Frame Group > Copy into new group: copy frames first..last (0-based) to the end of the timeline
        as a new group. Shows the message and does nothing if it cannot be done."""
        assert self.project is not None
        try:
            before = self.checkpoint()
            edit.check_copy(self.project, name, first, last)
            owner = groups.key_owner(self.project, key)
            if owner is not None and not messages.choose(self.parent_widget, groups.msg_move_key(key, owner, name),
                                                         "", "Move", "Cancel"):
                return False
            group = edit.copy_into_new_group(self.project, name, first, last, key, on_release, colour)
        except groups.GroupError as e:
            messages.warn(self.parent_widget, str(e))
            return False
        self.commit(before)
        self.frames_changed.emit()
        self.select(group.first)
        return True

    def set_start_state(self, rule: Rule | None) -> None:
        assert self.project is not None
        before = self.checkpoint()
        groups.set_start_state(self.project, rule)
        self.commit(before)
        self.frames_changed.emit()

    # ---- undo / redo (FR-2.2) ------------------------------------------------------------------
    def checkpoint(self) -> history.Snapshot:
        """Call before an edit; pass the result to commit() once the edit has been made."""
        return history.take(self.project)

    def commit(self, before: history.Snapshot) -> None:
        """Record the edit as one undo step, if it changed anything. While Edit mode is on nothing is recorded:
        leaving Edit mode with Apply records everything done in it as one step."""
        if self.edit.mode:
            self.project.dirty = True
            return
        if not before.same_as(history.take(self.project)):
            self.history.push(before)
            self.project.dirty = True
            self.history_changed.emit()

    def clear_history(self) -> None:
        """Saving clears the undo history (FR-2.2)."""
        self.history.clear()
        self.history_changed.emit()

    @property
    def can_undo(self) -> bool:
        return self.project is not None and self.history.can_undo

    @property
    def can_redo(self) -> bool:
        return self.project is not None and self.history.can_redo

    def undo(self) -> bool:
        return self._step(self.history.undo)

    def redo(self) -> bool:
        return self._step(self.history.redo)

    def _step(self, move) -> bool:
        if self.project is None:
            return False
        snap = move(history.take(self.project))
        if snap is None:
            return False
        history.restore(self.project, snap)
        self.selected = max(0, min(self.selected, len(self.project.frames) - 1))
        self.history_changed.emit()
        self.frames_changed.emit()
        self.selection_changed.emit(self.selected)
        return True

    def set_fps(self, fps: int) -> bool:
        """Frames per second of the open project (FR-3.2). Undoable."""
        p = self.project
        if p is None or fps == p.fps:
            return False
        before = self.checkpoint()
        p.fps = fps
        self.commit(before)
        self.frames_changed.emit()
        return True

    def apply_settings(self, new: settings_io.Settings) -> None:
        self.settings = new
        settings_io.save(new)
        self.settings_changed.emit()

    # ---- palette (FR-3.13) ---------------------------------------------------------------------
    def replace_colour(self, slot: int, new) -> bool:
        """Overwrite palette slot `slot` with `new` (snapped). Asks first if the colour is already in the
        palette, because merging frees a slot."""
        p = self.project
        if p is None:
            return False
        colours = p.palette()
        if not 0 <= slot < len(colours):
            return False
        if palette.is_duplicate(p, slot, new):
            if not messages.choose(self.parent_widget, "Merge these colours?",
                                   "The colour is already in the palette. Merging frees a slot.", "Merge", "Cancel"):
                return False
        if self.edit.mode and self.edit.floating is not None:
            self.edit.notice.emit("Press Enter to fix the paste or Esc to discard it first.")
            return False
        before = self.checkpoint()
        palette.replace_colour(p, colours[slot], new)
        self.edit.colour_replaced(colours[slot], snap_colour(new, p.system.bits))
        self.commit(before)
        self.frames_changed.emit()
        return True

    def set_transparent(self, slot: int) -> bool:
        p = self.project
        if p is None:
            return False
        colours = p.palette()
        if not 0 <= slot < len(colours) or colours[slot] == p.transparent:
            return False
        if self.edit.mode and self.edit.floating is not None:
            self.edit.notice.emit("Press Enter to fix the paste or Esc to discard it first.")
            return False
        before = self.checkpoint()
        palette.set_transparent(p, colours[slot])
        self.commit(before)
        self.frames_changed.emit()
        return True

    # ---- RunSpriteRun (FR-3.3, FR-3.10) -----------------------------------------------------------
    @property
    def running(self) -> bool:
        return self.runner is not None and self.runner.running

    def toggle_run(self) -> None:
        """F5: start RunSpriteRun, or stop it and return to the start state."""
        if self.runner is None or self.edit.mode:
            return
        if self.running:
            self.stop_run()
        else:
            self.runner.start()
            self.timer.start(round(1000 / self.project.fps))
            self.run_state.emit(True)
            self._show_run()

    def stop_run(self) -> None:
        if self.runner is None or not self.runner.running:
            return
        self.timer.stop()
        self.runner.stop()
        self.run_state.emit(False)
        self.keys_held.emit([])
        self._show_run()

    def start_with_key(self, key: str) -> bool:
        """RunSpriteRun is stopped and a key that has a Frame Group is pressed: start it (as F5 does) and
        play that group. Keys with no group do nothing."""
        if self.runner is None or self.running or self.edit.mode or not self.runner._matters(key):
            return False
        self.toggle_run()
        return self.key_press(key)

    def key_press(self, key: str) -> bool:
        if self.runner is not None and self.runner.press(key):
            self.keys_held.emit(self.runner.lit())
            self._show_run()
            return True
        return False

    def key_release(self, key: str) -> bool:
        if self.runner is not None and self.runner.release(key):
            self.keys_held.emit(self.runner.lit())
            self._show_run()
            return True
        return False

    def release_all_keys(self) -> None:
        if self.runner is not None and self.runner.held:
            self.runner.release_all()
            self.keys_held.emit([])
            self._show_run()

    def _tick(self) -> None:
        if self.runner is not None and self.runner.tick():
            self._show_run()

    def _show_run(self) -> None:
        self.run_frame.emit(self.runner.frame if self.runner else -1)

    def _frames_changed(self) -> None:
        """Frames or groups were edited: RunSpriteRun stops (showing the start state); when it was not
        running the window keeps showing the selected frame."""
        if self.runner is None:
            return
        was_running = self.running
        self.stop_run()
        self.runner.stop()                       # refreshes the start state after the edit
        if was_running:
            self._show_run()
        else:
            self._show_selected()

    def _selection_changed(self, _index: int) -> None:
        """Selecting a frame shows it in the RunSpriteRun window, unless RunSpriteRun is running."""
        if not self.running:
            self._show_selected()

    def _show_selected(self) -> None:
        self.run_frame.emit(self.selected if self.project and self.project.frames else -1)
