import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from src.app import messages
from src.app.main_window import MainWindow
from src.app.timeline import FIRST_X, PITCH, THUMB_Y, VISIBLE
from src.core.project import Frame, Group, Project
from src.core.systems import get_system


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def project(n=12, system="Atari ST", groups=()):
    frames = [Frame(f"f{i + 1}_{i + 1:03d}", Image.new("RGB", (8, 8), (73 * (i % 3), 0, 0))) for i in range(n)]
    return Project("P", get_system(system), 8, 8, transparent=(0, 0, 0), frames=frames, groups=list(groups), dirty=False)


@pytest.fixture
def win(app, monkeypatch):
    monkeypatch.setattr(messages, "warn", lambda *a, **k: shown.append(a[1]))
    monkeypatch.setattr(messages, "choose", lambda *a, **k: True)
    shown.clear()
    w = MainWindow()
    w.show()
    w.set_project(project(groups=[Group("A", 0, 1, colour=(255, 0, 0))]))
    return w


shown: list[str] = []


def tl(w):
    return w.panels["Timeline and frames"]


def test_timeline_shows_eight_and_scrolls(win):
    t = tl(win)
    assert sum(s.isVisibleTo(t) for s in t.slots) == VISIBLE
    assert t.slots[0].number.text() == "1" and t.bar.maximum() == 4
    t.scroll_by(1)
    assert t.slots[0].number.text() == "2" and t.slots[0].label.text() == "f2" and t.slots[0].suffix.text() == "_002"
    t.bar.setValue(4)
    assert t.slots[7].number.text() == "12" and not t.right.isEnabled()
    t.left.click()
    assert t.first == 3


def test_selection_follows_and_scrolls_into_view(win):
    t = tl(win)
    win.controller.select(11)
    assert t.first == 4 and win.panels["Frame view"].number.currentText() == "12"
    win.controller.select(0)
    assert t.first == 0 and win.panels["Frame view"].label.currentText() == "f1_001"
    t.slots[4].thumb.pressed.emit(4)
    assert win.controller.selected == 4


def test_group_row_and_border(win):
    t = tl(win)
    assert t.slots[0].group.text() == "A" and t.slots[2].group.text() == ""
    assert t.slots[0].thumb.border.red() == 255


def test_frame_view_dropdowns_select(win):
    fv = win.panels["Frame view"]
    fv.label.setCurrentIndex(5)
    fv.label.activated.emit(5)
    assert win.controller.selected == 5 and fv.number.currentText() == "6"


def test_rename_valid_and_refused(win):
    t = tl(win)
    s = t.slots[3]
    s.label.setText("Jump_1")
    s.label.editingFinished.emit()
    assert win.controller.project.frames[3].label == "Jump_1_004" and s.suffix.text() == "_004"
    s.label.setText("bad name")
    s.label.editingFinished.emit()
    assert shown[-1].startswith("Names can only use") and s.label.text() == "Jump_1"
    s.label.setText("")
    s.label.editingFinished.emit()
    assert shown[-1] == "A frame needs a name." and s.label.text() == "Jump_1"       # the old name returns
    s.label.setText("f1")                                                           # a name another frame has is fine
    s.label.editingFinished.emit()
    assert win.controller.project.frames[3].label == "f1_004"


def test_renaming_in_a_group_renames_the_group(win):
    t = tl(win)
    t.slots[1].label.setText("Idle")
    t.slots[1].label.editingFinished.emit()                  # frames 1 and 2 are group A
    assert [f.label for f in win.controller.project.frames][:3] == ["Idle_001", "Idle_002", "f3_003"]
    assert t.slots[0].label.text() == "Idle"
    win.controller.undo()
    assert [f.label for f in win.controller.project.frames][:3] == ["f1_001", "f2_002", "f3_003"]


def test_ctrl_move_and_keep_selection(win):
    win.controller.select(4)
    assert win.controller.move_selected(1)
    labels = [f.label for f in win.controller.project.frames]
    assert labels[4:6] == ["f6_005", "f5_006"] and win.controller.selected == 5


def test_drag_reorder_and_cancel(win):
    t = tl(win)
    def at(gap):                                       # a point on the boundary before frame `gap`
        return QPoint(FIRST_X - 3 + (gap - t.first) * PITCH, THUMB_Y + 30)
    t._drag_move(0, at(3))
    assert t.marker.isVisible()
    t._drag_end(0, at(3))                              # frame 1 dropped before frame 4
    assert [f.label for f in win.controller.project.frames][:4] == ["f2_001", "f3_002", "f1_003", "f4_004"]
    t._drag_move(2, at(7))
    t._drag_end(2, QPoint(5, 5))                       # dropped outside the strip: nothing changes
    assert [f.label for f in win.controller.project.frames][:4] == ["f2_001", "f3_002", "f1_003", "f4_004"]
    t._drag_move(2, at(7))
    t._cancel_drag()                                   # Esc
    assert not t.marker.isVisible() and win.controller.project.frames[2].label == "f1_003"


def test_palette_panel_counts_and_free_slots(win):
    pp = win.panels["Palette panel"]
    assert pp.count.text() == "3 used, 13 free of 16"
    assert pp.grid.slots == 16 and len(pp.grid.colours) == 3
    win.set_project(project(system="Amiga"))
    assert pp.grid.slots == 32 and pp.count.text().endswith("of 32")


def test_frame_view_scale_and_transparent(win):
    v = win.panels["Frame view"].view
    img = v.grab().toImage()
    assert img.pixelColor(128, 128).red() in (0, 73, 146)     # drawn, not blank


def test_long_frame_lists_drop_down_as_a_short_scrolling_list(win):
    fv = win.panels["Frame view"]
    assert fv.number.maxVisibleItems() == 10 and fv.label.maxVisibleItems() == 10
    assert "combobox-popup: 0" in fv.number.styleSheet()


# ---- Timeline copy / paste ----
def _ctrl(widget, key):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    widget.window().activateWindow()                     # shortcuts only fire in the active window
    QApplication.processEvents()
    QTest.keyClick(widget, key, Qt.ControlModifier)


def _paste_dialog(monkeypatch, after=True, accept=True):
    from src.app import timeline
    seen = []

    def fake_exec(self):
        seen.append(self.windowTitle())
        (self.after if after else self.before).setChecked(True)
        return 1 if accept else 0
    monkeypatch.setattr(timeline.PasteFrameDialog, "exec", fake_exec)
    return seen


def test_ctrl_c_ctrl_v_pastes_after_with_dialog_and_undo(win, monkeypatch):
    from PySide6.QtCore import Qt
    c, t = win.controller, tl(win)
    seen = _paste_dialog(monkeypatch)
    t.slots[2].thumb.pressed.emit(2)                      # click frame 3 (f3): the panel now has the focus
    _ctrl(t, Qt.Key_C)
    assert c.frame_clipboard is not None and c.frame_clipboard.label == "f3_003"
    t.slots[5].thumb.pressed.emit(5)                      # select f6: Before / After still refer to the copied f3
    _ctrl(t, Qt.Key_V)
    labels = [f.label for f in c.project.frames]
    assert seen == ["Paste frame"] and len(labels) == 13 and labels[2:4] == ["f3_003", "f3_004"] and labels[6] == "f6_007" and c.selected == 3
    assert c.history.can_undo
    c.undo()
    assert len(c.project.frames) == 12


def test_paste_before_and_cancel(win, monkeypatch):
    from PySide6.QtCore import Qt
    c, t = win.controller, tl(win)
    t.slots[0].thumb.pressed.emit(0)
    _ctrl(t, Qt.Key_C)
    t.slots[4].thumb.pressed.emit(4)
    _paste_dialog(monkeypatch, accept=False)
    _ctrl(t, Qt.Key_V)
    assert len(c.project.frames) == 12 and c.frame_clipboard is not None      # cancelled: nothing changes
    _paste_dialog(monkeypatch, after=False)
    _ctrl(t, Qt.Key_V)
    assert c.project.frames[0].label == "f1_001" and c.project.frames[1].label == "f1_002" and c.selected == 0
    assert (c.project.groups[0].first, c.project.groups[0].last) == (0, 2)      # the copy joined its own group A


def test_paste_with_nothing_copied_does_nothing(win, monkeypatch):
    from PySide6.QtCore import Qt
    t = tl(win)
    seen = _paste_dialog(monkeypatch)
    t.slots[0].thumb.pressed.emit(0)
    _ctrl(t, Qt.Key_V)
    assert seen == [] and len(win.controller.project.frames) == 12 and not shown


def test_clicking_out_of_the_timeline_drops_the_copy(win, monkeypatch):
    from PySide6.QtCore import Qt
    c, t = win.controller, tl(win)
    t.slots[0].thumb.pressed.emit(0)
    _ctrl(t, Qt.Key_C)
    assert c.frame_clipboard is not None
    other = win.panels["Frame view"]
    other.setFocusPolicy(Qt.StrongFocus)
    other.setFocus()
    QApplication.processEvents()
    assert c.frame_clipboard is None


def test_right_click_copy_before_and_after(win, monkeypatch):
    from src.app.timeline import TimelinePanel
    c, t = win.controller, tl(win)
    pick = {"text": "Copy after"}
    monkeypatch.setattr(TimelinePanel, "_exec_menu",
                        lambda self, menu, pos: next(a for a in menu.actions() if a.text() == pick["text"]))
    t.slots[2].thumb.menu_requested.emit(2, QPoint(0, 0))
    assert [f.label for f in c.project.frames][2:4] == ["f3_003", "f3_004"] and c.selected == 3
    pick["text"] = "Copy before"
    t.slots[0].thumb.menu_requested.emit(0, QPoint(0, 0))
    assert [f.label for f in c.project.frames][:2] == ["f1_001", "f1_002"] and c.selected == 0
    assert c.frame_clipboard is None                      # the menu needs no Ctrl+C


def test_shortcuts_do_nothing_in_edit_mode(win, monkeypatch):
    from PySide6.QtCore import Qt
    c, t = win.controller, tl(win)
    t.slots[1].thumb.pressed.emit(1)
    c.edit.begin()
    _ctrl(t, Qt.Key_C)
    assert c.frame_clipboard is None
    assert not c.clone_frame(1, True) and len(c.project.frames) == 12


def test_paste_does_nothing_when_the_copied_frame_is_gone(win, monkeypatch):
    from PySide6.QtCore import Qt
    c, t = win.controller, tl(win)
    seen = _paste_dialog(monkeypatch)
    t.slots[4].thumb.pressed.emit(4)
    _ctrl(t, Qt.Key_C)
    _ctrl(t, Qt.Key_V)                                    # a copy lands after frame 5 (index 5)
    assert len(c.project.frames) == 13
    t.slots[5].thumb.pressed.emit(5)
    _ctrl(t, Qt.Key_C)                                    # copy the copy ...
    c.undo()                                              # ... then Undo removes it
    assert len(c.project.frames) == 12 and c.copied_index() is None
    seen.clear()
    _ctrl(t, Qt.Key_V)
    assert seen == [] and len(c.project.frames) == 12 and not shown


def test_copied_frame_is_still_found_after_undo_and_moves(win, monkeypatch):
    from PySide6.QtCore import Qt
    c, t = win.controller, tl(win)
    t.slots[4].thumb.pressed.emit(4)
    _ctrl(t, Qt.Key_C)
    c.move_frame(4, 0)                                    # the copied frame moves ...
    assert c.copied_index() == 0
    c.undo()                                              # ... and Undo brings it back as the same frame
    assert c.copied_index() == 4
