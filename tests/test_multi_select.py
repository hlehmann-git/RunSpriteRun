"""Timeline multi-select (Ctrl+click, Shift+click), Delete, and copy / paste of several frames."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.app import messages
from src.app.main_window import MainWindow
from src.core.edit import EditError, clone_frames, delete_frames, plan_delete
from src.core.project import Frame, Group, Project, Rule
from src.core.systems import get_system


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def make(n=12, groups=()):
    frames = [Frame(f"f{i}_{i + 1:03d}", Image.new("RGB", (8, 8), (73 * (i % 3), 0, 0))) for i in range(n)]
    return Project("P", get_system("Atari ST"), 8, 8, transparent=(0, 0, 0), frames=frames, groups=list(groups), dirty=False)


def labels(p):
    return [f.label for f in p.frames]


# ---- core: delete -------------------------------------------------------------------------------------
def test_delete_renumbers_and_shrinks_groups():
    p = make(groups=[Group("A", 1, 4), Group("B", 6, 8)])
    plan = delete_frames(p, [2, 3, 7])
    assert plan.emptied == [] and len(p.frames) == 9
    assert labels(p)[:4] == ["f0_001", "f1_002", "f4_003", "f5_004"]
    assert [(g.name, g.first, g.last) for g in p.groups] == [("A", 1, 2), ("B", 4, 5)]
    assert p.dirty


def test_delete_a_whole_group_removes_it_and_resets_rules():
    p = make(groups=[Group("A", 1, 2), Group("B", 5, 6, on_release=Rule("group", "A"))])
    p.start_state = Rule("frame", "f9_010")
    plan = plan_delete(p, [1, 2, 9])
    assert plan.emptied == ["A"] and plan.resets == ["group B (On Release)", "Start state"]
    delete_frames(p, [1, 2, 9])
    assert [g.name for g in p.groups] == ["B"] and (p.groups[0].first, p.groups[0].last) == (3, 4)
    assert p.groups[0].on_release is None and p.start_state is None


def test_rules_to_surviving_frames_follow_the_renumbering():
    p = make(groups=[Group("A", 5, 6, on_release=Rule("frame", "f8_009"))])
    delete_frames(p, [0, 1])
    assert p.frames[6].label == "f8_007" and p.groups[0].on_release.target == "f8_007"


def test_cannot_delete_every_frame_or_nothing():
    p = make(3)
    with pytest.raises(EditError, match="at least one frame"):
        delete_frames(p, [0, 1, 2])
    with pytest.raises(EditError):
        delete_frames(p, [])
    with pytest.raises(EditError):
        delete_frames(p, [7])
    assert len(p.frames) == 3


# ---- core: paste a block ------------------------------------------------------------------------------
def test_clone_frames_after_joins_group_and_numbers():
    p = make(groups=[Group("A", 2, 4)])
    srcs = [Frame(p.frames[2].label, p.frames[2].image), Frame(p.frames[4].label, p.frames[4].image)]
    first = clone_frames(p, srcs, 4, True)                       # after frame 5, the last of group A
    assert first == 5 and len(p.frames) == 14
    assert labels(p)[5:7] == ["f2_006", "f4_007"] and (p.groups[0].first, p.groups[0].last) == (2, 6)


def test_clone_frames_before_and_limit():
    p = make(6)
    srcs = [Frame("a_001", p.frames[0].image), Frame("b_002", p.frames[1].image)]
    assert clone_frames(p, srcs, 3, False) == 3 and labels(p)[3:5] == ["a_004", "b_005"]
    big = make(119)
    with pytest.raises(EditError, match="at most 120"):
        clone_frames(big, srcs, 0, True)
    assert len(big.frames) == 119


# ---- window ---------------------------------------------------------------------------------------------
asked = []


@pytest.fixture
def win(app, monkeypatch):
    asked.clear()
    monkeypatch.setattr(messages, "warn", lambda *a, **k: asked.append(("warn", a[1])))
    monkeypatch.setattr(messages, "choose", lambda p, t, d, y, n: (asked.append((t, d)), True)[1])
    w = MainWindow()
    w.show()
    w.set_project(make(groups=[Group("A", 1, 2, colour=(255, 0, 0))]))
    w.activateWindow()
    QApplication.processEvents()
    return w


def timeline(w):
    return w.panels["Timeline and frames"]


def click(t, slot, mods=Qt.NoModifier):
    thumb = t.slots[slot].thumb
    thumb.mods = mods
    thumb.pressed.emit(slot)
    thumb.mods = Qt.NoModifier


def test_plain_click_selects_one(win):
    c, t = win.controller, timeline(win)
    click(t, 3)
    assert c.selection() == [3]


def test_ctrl_and_shift_click_need_the_timeline_to_have_the_focus(win):
    c, t = win.controller, timeline(win)
    win.panels["Frame view"].setFocus()                              # the last click was somewhere else
    QApplication.processEvents()
    click(t, 4, Qt.ControlModifier)
    assert c.selection() == [4]                                      # acts as a plain click
    click(t, 6, Qt.ControlModifier)
    assert c.selection() == [4, 6]                                   # now it adds
    click(t, 6, Qt.ControlModifier)
    assert c.selection() == [4]                                      # and removes
    click(t, 4, Qt.ControlModifier)
    assert c.selection() == [4]                                      # the main frame stays


def test_shift_click_selects_the_range_from_the_first_frame(win):
    c, t = win.controller, timeline(win)
    click(t, 2)
    click(t, 5, Qt.ShiftModifier)
    assert c.selection() == [2, 3, 4, 5] and c.selected == 2
    click(t, 0, Qt.ShiftModifier)
    assert c.selection() == [0, 1, 2] and c.selected == 2
    click(t, 7)
    assert c.selection() == [7]


def test_overlay_flags(win):
    c, t = win.controller, timeline(win)
    click(t, 1)
    assert not any(s.thumb.chosen for s in t.slots)                  # one frame: no overlay
    click(t, 3, Qt.ControlModifier)
    chosen = [s.thumb.chosen for s in t.slots[:5]]
    assert chosen == [False, True, False, True, False] and t.slots[1].thumb.main and not t.slots[3].thumb.main


def test_no_multi_select_in_edit_mode(win):
    c, t = win.controller, timeline(win)
    click(t, 1)
    c.edit.mode = True
    c.select_extra(3, False)
    assert c.selection() == [1]
    assert c.delete_selected() is False and len(c.project.frames) == 12
    c.edit.mode = False


def test_delete_key_asks_deletes_selects_and_undo_restores(win):
    c, t = win.controller, timeline(win)
    click(t, 1)
    click(t, 2, Qt.ShiftModifier)                                    # frames 2 and 3: all of group A
    QTest.keyClick(t, Qt.Key_Delete)
    assert asked[-1][0] == "Delete these 2 frames?" and "Group A has no frames left" in asked[-1][1]
    assert len(c.project.frames) == 10 and c.project.groups == [] and c.selected == 1 and c.selection() == [1]
    assert labels(c.project)[1] == "f3_002"
    c.undo()
    assert len(c.project.frames) == 12 and [g.name for g in c.project.groups] == ["A"]


def test_delete_one_frame_and_declined(win, monkeypatch):
    c, t = win.controller, timeline(win)
    click(t, 5)
    monkeypatch.setattr(messages, "choose", lambda *a, **k: False)
    QTest.keyClick(t, Qt.Key_Delete)
    assert len(c.project.frames) == 12                               # declined: nothing happens
    monkeypatch.setattr(messages, "choose", lambda p, tt, d, y, n: (asked.append((tt, d)), True)[1])
    QTest.keyClick(t, Qt.Key_Delete)
    assert asked[-1][0] == "Delete this frame?" and len(c.project.frames) == 11 and c.selected == 5


def test_delete_last_frames_refused(win):
    c, t = win.controller, timeline(win)
    click(t, 0)
    c.select_extra(11, True)
    assert c.delete_selected() is False and asked[-1][0] == "warn" and len(c.project.frames) == 12


def test_delete_key_is_ignored_while_typing_a_name(win):
    c, t = win.controller, timeline(win)
    click(t, 2)
    t.slots[2].label.setFocus()
    QApplication.processEvents()
    QTest.keyClick(t.slots[2].label, Qt.Key_Delete)
    assert len(c.project.frames) == 12 and not any(a[0].startswith("Delete") for a in asked)


def test_copy_and_paste_several_frames(win, monkeypatch):
    from src.app import timeline as tlmod
    c, t = win.controller, timeline(win)
    seen = []

    def fake_exec(self):
        seen.append(self.windowTitle())
        self.after.setChecked(True)
        return 1
    monkeypatch.setattr(tlmod.PasteFrameDialog, "exec", fake_exec)
    click(t, 3)
    click(t, 3 + 0, Qt.NoModifier)
    click(t, 5, Qt.ControlModifier)                                  # frames 4 and 6
    QTest.keyClick(t, Qt.Key_C, Qt.ControlModifier)
    assert [f.label for f in c.clipboard_frames] == ["f3_004", "f5_006"]
    click(t, 0)
    QTest.keyClick(t, Qt.Key_V, Qt.ControlModifier)
    assert seen == ["Paste frames"] and len(c.project.frames) == 14
    assert labels(c.project)[6:8] == ["f3_007", "f5_008"] and c.selected == 6 and c.selection() == [6]
    c.undo()
    assert len(c.project.frames) == 12


def test_right_click_copy_before_uses_the_whole_selection(win):
    c, t = win.controller, timeline(win)
    click(t, 6)
    click(t, 7, Qt.ShiftModifier)
    assert c.clone_frame(7, False) is True                          # Copy before: before the first selected frame
    assert len(c.project.frames) == 14 and labels(c.project)[6:8] == ["f6_007", "f7_008"]


def test_no_moving_with_several_frames_selected(win):
    c, t = win.controller, timeline(win)
    click(t, 3)
    click(t, 4, Qt.ShiftModifier)
    before = labels(c.project)
    assert c.move_selected(1) is False and labels(c.project) == before
