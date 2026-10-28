"""Holds the open project and the selected frame, and tells the panels when something changed.
Panels only display this state and pass user actions here (section 6.1)."""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QWidget

from src.app import messages
from src.app.edit_session import EditSession
from src.core import edit, editing, groups, history, palette
from src.core.project import Frame, Project, Rule
from src.core.runner import Runner
from src.io import settings as settings_io


MSG_PALETTE_FULL = ("The palette is full.", "Delete a colour or reduce the palette first.")
MSG_ALREADY_IN_PALETTE = ("That colour is already in the palette.", "Choose a different primary colour first.")


class Controller(QObject):
    project_changed = Signal()        # a different project is open (or none)
    selection_changed = Signal(int)   # the selected frame (0-based)
    multi_changed = Signal()          # Ctrl+click / Shift+click changed the set of selected frames
    frames_changed = Signal()         # frame order, labels or groups changed
    playing_frame = Signal(int)       # frame being shown by a playing view, or -1 when none is playing
    run_frame = Signal(int)           # frame the RunSpriteRun window shows (always: the start state when stopped)
    run_state = Signal(bool)          # RunSpriteRun started or stopped
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
        self.multi: set[int] = set()       # more selected frames besides `selected` (the frame clicked first)
        self.parent_widget = parent_widget
        self.runner: Runner | None = None
        self.history = history.History()
        self.edit = EditSession(self)
        self.eyedropper_armed = False      # set by the Colour editor
        self.clipboard_frames: list[Frame] = []      # Ctrl+C in the Timeline: the frames as they were when copied
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.frames_changed.connect(self._frames_changed)
        self.selection_changed.connect(self._selection_changed)
        self.project_changed.connect(self.drop_frame_clipboard)

    def set_project(self, project: Project | None) -> None:
        self.stop_run()
        self.edit.reset()
        self.project = project
        self.history.clear()
        self.history_changed.emit()
        self.runner = Runner(project) if project is not None else None
        self.selected = 0
        self.multi.clear()
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
        self.multi.clear()                                       # a plain click goes back to one frame
        self.selection_changed.emit(index)
        self.multi_changed.emit()

    @property
    def frame_clipboard(self) -> Frame | None:
        """The first copied frame, or None when nothing is copied."""
        return self.clipboard_frames[0] if self.clipboard_frames else None

    def selection(self) -> list[int]:
        """Every selected frame, in timeline order."""
        return sorted({self.selected} | self.multi)

    def select_extra(self, index: int, range_: bool) -> None:
        """Ctrl+click (add or remove one frame) or Shift+click (the range from the frame clicked first). The frame clicked
        first stays the main one; nothing happens in Edit mode."""
        if self.project is None or self.edit.mode or not 0 <= index < len(self.project.frames):
            return
        if range_:
            lo, hi = sorted((self.selected, index))
            self.multi = set(range(lo, hi + 1)) - {self.selected}
        elif index != self.selected:
            self.multi ^= {index}
        self.multi_changed.emit()

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

    # ---- copy and paste frames in the timeline -------------------------------------------------
    def copy_frame(self) -> bool:
        """Ctrl+C in the Timeline: remember the selected frames."""
        if self.project is None or not self.project.frames or self.edit.mode:
            return False
        self.clipboard_frames = [Frame(f.label, f.image, layers=f.layers, uid=f.uid)
                                 for f in (self.project.frames[i] for i in self.selection())]
        return True

    def drop_frame_clipboard(self) -> None:
        self.clipboard_frames = []

    def copied_indices(self, srcs: list[Frame] | None = None) -> list[int]:
        """Where the copied frames are now (those that still exist), in timeline order."""
        srcs = srcs if srcs is not None else self.clipboard_frames
        if self.project is None or not srcs:
            return []
        wanted = {f.uid for f in srcs}
        return [i for i, f in enumerate(self.project.frames) if f.uid in wanted]

    def copied_index(self, src: Frame | None = None) -> int | None:
        """Where the (first) copied frame is now, or None when there is nothing copied or the frame is gone."""
        found = self.copied_indices([src] if src is not None else None)
        return found[0] if found else None

    def paste_frame(self, after: bool, src: Frame | None = None, srcs: list[Frame] | None = None) -> bool:
        """Insert copies of the copied frames (`srcs`, or `src`, default: the remembered frames) as one block before the
        first of them or after the last of them, as one Undo step. Does nothing if they no longer exist."""
        if srcs is None:
            srcs = [src] if src is not None else self.clipboard_frames
        found = self.copied_indices(srcs)
        if self.project is None or self.edit.mode or not found:
            return False
        current = {f.uid: f for f in self.project.frames}
        pieces = [Frame(current[f.uid].label, f.image, layers=f.layers) for f in sorted(
            (f for f in srcs if f.uid in current), key=lambda f: self.project.frames.index(current[f.uid]))]
        ref = found[-1] if after else found[0]
        self.stop_run()
        before = self.checkpoint()
        try:
            idx = edit.clone_frames(self.project, pieces, ref, after)
        except edit.EditError as e:
            messages.warn(self.parent_widget, str(e))
            return False
        self.commit(before)
        self.selected = idx
        self.multi.clear()
        self.frames_changed.emit()
        self.selection_changed.emit(idx)
        return True

    def clone_frame(self, index: int, after: bool) -> bool:
        """Right-click Copy before / Copy after: copy the selected frames (or just frame `index` if it is not one of
        them) next to themselves."""
        if self.project is None or self.edit.mode or not 0 <= index < len(self.project.frames):
            return False
        if index not in self.selection():
            self.select(index)
        chosen = [self.project.frames[i] for i in self.selection()]
        return self.paste_frame(after, srcs=[Frame(f.label, f.image, layers=f.layers, uid=f.uid) for f in chosen])

    # ---- delete frames ---------------------------------------------------------------------------
    def delete_selected(self) -> bool:
        """The Delete key in the Timeline: ask, then remove the selected frames (Undo brings them back)."""
        if self.project is None or self.edit.mode or not self.project.frames:
            return False
        idx = self.selection()
        try:
            plan = edit.plan_delete(self.project, idx)
        except edit.EditError as e:
            messages.warn(self.parent_widget, str(e))
            return False
        title = "Delete this frame?" if len(idx) == 1 else f"Delete these {len(idx)} frames?"
        lines = ["You can undo this."]
        if plan.emptied:
            lines.append("Group " + ", ".join(plan.emptied) + " has no frames left and will be deleted.")
        if plan.resets:
            lines.append("These rules pointed to what is deleted and will be reset: " + ", ".join(plan.resets) + ".")
        if not messages.choose(self.parent_widget, title, "\n".join(lines), "Delete", "Cancel"):
            return False
        self.stop_run()
        before = self.checkpoint()
        edit.delete_frames(self.project, idx)
        self.commit(before)
        self.selected = min(idx[0], len(self.project.frames) - 1)
        self.multi.clear()
        self.frames_changed.emit()
        self.selection_changed.emit(self.selected)
        return True

    def move_selected(self, delta: int) -> bool:
        """Ctrl+Left / Ctrl+Right: move the selected frame one place."""
        if self.project is None or self.multi:
            return False                                   # several selected frames are not moved
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

    # ---- Frame Group Control (rules) ----------------------------------------------------------
    def set_control_rules(self, rules) -> bool:
        """Replace the Frame Group Control rule list (one Undo step). Shows the message and does nothing if a rule is not valid."""
        assert self.project is not None
        try:
            before = self.checkpoint()
            groups.set_control_rules(self.project, rules)
        except groups.GroupError as e:
            messages.warn(self.parent_widget, str(e))
            return False
        self.commit(before)
        self.frames_changed.emit()
        return True

    def set_transitions(self, transitions) -> bool:
        """Replace the Frame Group Control transition list (one Undo step). Shows the message and does nothing if one is not valid."""
        assert self.project is not None
        try:
            before = self.checkpoint()
            groups.set_transitions(self.project, transitions)
        except groups.GroupError as e:
            messages.warn(self.parent_widget, str(e))
            return False
        self.commit(before)
        self.frames_changed.emit()
        return True

    def set_rules_and_transitions(self, rules, transitions, group_keys: dict | None = None) -> bool:
        """Replace the Frame Group Control rules and transitions together, and the Group keys changes made in that window
        (`group_keys`: group name -> [key, on_release]): one Undo step (the Apply of the Frame Group Control window)."""
        assert self.project is not None
        before = self.checkpoint()
        try:
            groups.set_control_rules(self.project, rules)
            groups.set_transitions(self.project, transitions)
            if group_keys:
                for name in group_keys:                          # clear first, so keys can swap between groups
                    if groups.find_group(self.project, name) is not None:
                        groups.set_group_key(self.project, name, None)
                for name, (key, release) in group_keys.items():
                    if groups.find_group(self.project, name) is not None:
                        groups.set_group_key(self.project, name, key)
                        groups.set_group_release(self.project, name, release)
        except groups.GroupError as e:
            history.restore(self.project, before)                # nothing is changed partly
            messages.warn(self.parent_widget, str(e))
            return False
        self.commit(before)
        self.frames_changed.emit()
        return True

    def set_group_key(self, name: str, key) -> bool:
        """The basic key of a group, edited in the Frame Group Control window. A key another group uses is moved after asking."""
        assert self.project is not None
        try:
            before = self.checkpoint()
            owner = groups.key_owner(self.project, key, ignore=name)
            if owner is not None and not messages.choose(self.parent_widget, groups.msg_move_key(key, owner, name),
                                                         "", "Move", "Cancel"):
                return False
            groups.set_group_key(self.project, name, key)
        except groups.GroupError as e:
            messages.warn(self.parent_widget, str(e))
            return False
        self.commit(before)
        self.frames_changed.emit()
        return True

    def set_group_release(self, name: str, rule: Rule | None) -> bool:
        assert self.project is not None
        try:
            before = self.checkpoint()
            groups.set_group_release(self.project, name, rule)
        except groups.GroupError as e:
            messages.warn(self.parent_widget, str(e))
            return False
        self.commit(before)
        self.frames_changed.emit()
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
        if self.timer.isActive():
            self.timer.setInterval(round(1000 / fps))      # RunSpriteRun is running: change its speed at once
        self.commit(before)
        self.frames_changed.emit()
        return True

    def apply_settings(self, new: settings_io.Settings) -> None:
        self.settings = new
        settings_io.save(new)
        self.settings_changed.emit()

    # ---- + colour -------------------------------------------------------------------------------
    def add_colour_blocked(self) -> str | None:
        """None if the + colour button can be used, otherwise why it is greyed out (no project, or fixed colours).
        A full palette is not a reason to grey it out: the button then says why it cannot add."""
        p = self.project
        if p is None:
            return "No project is open"
        if p.system.is_fixed:
            return "The colours of this system are fixed"
        return None

    def add_primary_colour(self) -> tuple[str, str] | None:
        """+ colour: add the primary colour to the next free palette slot straight away (one Undo step). Returns
        None when it was added, otherwise the message to show (text and detail) and nothing changes."""
        p = self.project
        reason = self.add_colour_blocked()
        if reason is not None:
            return reason + ".", None
        if len(p.palette()) >= p.system.max_colours:
            return MSG_PALETTE_FULL
        if self.edit.mode and self.edit.floating is not None:
            return "Press Enter to fix the paste or Esc to discard it first.", None
        colour = p.system.snap(self.edit.active)
        if colour in p.palette():
            return MSG_ALREADY_IN_PALETTE
        self.edit.editor_colour = colour
        self.edit.add_colour()                          # the Pencil with the new colour is ready (in Edit mode)
        return None

    # ---- palette (FR-3.13) ---------------------------------------------------------------------
    def delete_colour_blocked(self, slot: int) -> str | None:
        """None if the colour in palette slot `slot` can be deleted, otherwise the reason it can't."""
        p = self.project
        if p is None:
            return "No project is open"
        colours = p.palette()
        if not 0 <= slot < len(colours):
            return "That colour is not in the palette"
        if self.edit.mode and self.edit.floating is not None:
            return "Press Enter to fix the paste or Esc to discard it first."
        if self.edit.mode and self.edit.history_uses(colours[slot]):
            return "This colour is used by an earlier edit step (Undo)"
        return editing.can_delete_colour(p, colours[slot])

    def delete_colour(self, slot: int) -> bool:
        """Delete an unused colour from the palette (the squares after it move up one place)."""
        if self.delete_colour_blocked(slot) is not None:
            return False
        p = self.project
        before = self.checkpoint()
        editing.delete_colour(p, p.palette()[slot])
        self.commit(before)
        self.frames_changed.emit()
        return True

    def move_colour(self, from_slot: int, to_slot: int) -> bool:
        """Move a palette colour to another slot; the colours between move along one place. Only the order changes,
        never a pixel. One Undo step (outside Edit mode)."""
        p = self.project
        if p is None:
            return False
        colours = p.palette()
        if not (0 <= from_slot < len(colours) and 0 <= to_slot < len(colours)) or from_slot == to_slot:
            return False
        if self.edit.mode and self.edit.floating is not None:
            self.edit.notice.emit("Press Enter to fix the paste or Esc to discard it first.")
            return False
        before = self.checkpoint()
        colour = colours.pop(from_slot)
        colours.insert(to_slot, colour)
        p.extra_colours = colours
        self.commit(before)
        self.frames_changed.emit()
        return True

    def replace_colour(self, slot: int, new) -> bool:
        """Overwrite palette slot `slot` with `new` (snapped). Asks first if the colour is already in the
        palette, because merging frees a slot."""
        p = self.project
        if p is None or p.system.is_fixed:                  # the colours of a fixed-palette system cannot be changed
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
        self.edit.colour_replaced(colours[slot], p.system.snap(new))
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
        """Start RunSpriteRun, or stop it and return to the start state."""
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
        """RunSpriteRun is stopped and a key that has a Frame Group is pressed: start it and
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
        if self.runner is not None and self.runner._physical:
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
        self.multi.clear()                      # frame numbers may have changed: back to one selected frame
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
