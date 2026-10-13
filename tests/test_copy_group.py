import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.app import messages
from src.app.main_window import MainWindow
from src.core import edit, groups
from src.core.project import Frame, Group, Project, Rule
from src.core.rules import copy_label
from src.core.systems import get_system
from src.io.project_file import open_project, save_project


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def log(monkeypatch):
    out = {"warn": [], "choose": [], "answer": True, "copy": True}
    monkeypatch.setattr(messages, "warn", lambda p, t, d=None: out["warn"].append(t))
    monkeypatch.setattr(messages, "info", lambda p, t, d=None: None)
    monkeypatch.setattr(messages, "choose", lambda p, t, d, y, n: (out["choose"].append(t), out["answer"])[1])
    monkeypatch.setattr(messages, "overlap", lambda p, t: (out["warn"].append(t), out["copy"])[1])
    return out


def make_project(n=12):
    frames = [Frame(f"f{i + 1}", Image.new("RGB", (8, 8), (17 * (i % 3), 0, 0))) for i in range(n)]
    return Project("P", get_system("Amiga"), 8, 8, frames=frames,
                   groups=[Group("Idle", 0, 3, key="S"), Group("Right", 4, 7, key="D")], dirty=False)


@pytest.fixture
def win(app, log):
    w = MainWindow()
    w.show()
    w.set_project(make_project())
    return w


def fill(p, name, first, last, key="None"):
    p.name.setText(name)
    p.from_box.setValue(first)
    p.to_box.setValue(last)
    p.key.setCurrentText(key)


def test_copy_label_suffix_counts_up():
    assert copy_label("Idle_1", {"Idle_1"}) == "Idle_1_001"
    assert copy_label("Idle_1", {"Idle_1", "Idle_1_001"}) == "Idle_1_002"
    long = "a" * 40
    assert len(copy_label(long, {long})) == 40 and copy_label(long, {long}).endswith("_001")


def test_core_copy_appends_frames_and_group():
    p = make_project()
    g = edit.copy_into_new_group(p, "Copy", 1, 2, "W", Rule("frame", "f1"), (9, 9, 9))
    assert [f.label for f in p.frames[12:]] == ["f2_001", "f3_001"] and all(f.copied for f in p.frames[12:])
    assert not any(f.copied for f in p.frames[:12])
    assert (g.first, g.last, g.key) == (12, 13, "W")
    assert p.frames[12].image is p.frames[1].image or p.frames[12].image.tobytes() == p.frames[1].image.tobytes()
    edit.copy_into_new_group(p, "Again", 1, 1, None, None, (0, 0, 0))
    assert p.frames[14].label == "f2_002"


def test_core_copy_limits():
    p = make_project(119)
    with pytest.raises(groups.GroupError, match="This is exceeding the frame limit."):
        edit.copy_into_new_group(p, "Big", 0, 1, None, None, (0, 0, 0))
    assert len(p.frames) == 119 and len(p.groups) == 2             # nothing changed
    edit.copy_into_new_group(p, "One", 0, 0, None, None, (0, 0, 0))
    assert len(p.frames) == 120


def test_rename_clears_red_and_checks_duplicates():
    p = make_project()
    edit.copy_into_new_group(p, "Copy", 0, 0, None, None, (0, 0, 0))
    assert p.frames[12].copied
    with pytest.raises(edit.EditError):
        edit.rename_label(p, 12, "f1")
    assert p.frames[12].copied                                     # refused: still red
    edit.rename_label(p, 12, "walk")
    assert not p.frames[12].copied


def test_overlap_message_copy_button_makes_new_group(win, log):
    panel = win.set_frame_group
    panel.new_group()
    fill(panel, "Dup", 2, 5, "W")                                  # frames 2 to 5 belong to Idle and Right
    panel.apply()
    c = win.controller
    p = c.project
    assert "already belong" in log["warn"][0]
    assert len(p.frames) == 16 and p.groups[-1].name == "Dup" and (p.groups[-1].first, p.groups[-1].last) == (12, 15)
    assert [f.label for f in p.frames[12:]] == ["f2_001", "f3_001", "f4_001", "f5_001"]
    assert c.selected == 12 and panel.current == "Dup"
    assert win.info_bar.label.text().endswith("Frames: 16   |   Frame Groups: 3")
    tl = win.panels["Timeline and frames"]
    slot = next(sl for sl in tl.slots if sl.number.text() == "13")      # the first copied frame
    assert slot.label.text() == "f2_001"
    assert "#c0392b" in slot.label.styleSheet() and "#ffffff" in slot.label.styleSheet()
    c.undo()
    assert len(p.frames) == 12 and len(p.groups) == 2
    c.redo()
    assert len(p.frames) == 16 and p.frames[12].copied


def test_overlap_message_ok_does_nothing(win, log):
    log["copy"] = False
    panel = win.set_frame_group
    panel.new_group()
    fill(panel, "Dup", 2, 5)
    assert panel.apply() is False
    assert len(win.controller.project.frames) == 12 and len(win.controller.project.groups) == 2


def test_copy_over_frame_limit_shows_message_and_does_nothing(app, log):
    w = MainWindow()
    w.show()
    w.set_project(_full())
    panel = w.set_frame_group
    panel.new_group()
    fill(panel, "Dup", 2, 3)
    assert panel.apply() is False
    assert log["warn"][-1] == "This is exceeding the frame limit." and len(w.controller.project.frames) == 120


def _full():
    p = make_project(120)
    p.groups = [Group("Idle", 0, 3), Group("Right", 4, 7)]
    return p


def test_copy_with_taken_key_asks_to_move(win, log):
    panel = win.set_frame_group
    panel.new_group()
    fill(panel, "Dup", 2, 3, "S")                                  # S belongs to Idle
    panel.apply()
    assert log["choose"][-1] == "Move key S from Idle to Dup?"
    assert win.controller.project.groups[0].key is None
    assert [g.name for g in win.controller.project.groups if g.key == "S"] == ["Dup"]


def test_copy_keeps_name_and_group_rules(win, log):
    panel = win.set_frame_group
    panel.new_group()
    fill(panel, "idle", 2, 3)                                      # same name as an existing group
    panel.apply()
    assert "already exists" in log["warn"][-1] and len(win.controller.project.frames) == 12


def test_edit_group_overlap_has_no_copy_button(win, log):
    panel = win.set_frame_group
    panel._chosen(1)                                               # edit Idle
    panel.to_box.setValue(6)                                       # now overlaps Right
    log["copy"] = True
    assert panel.apply() is False
    assert len(win.controller.project.frames) == 12


def test_red_labels_persist_in_rsr(tmp_path):
    p = make_project()
    edit.copy_into_new_group(p, "Copy", 0, 1, None, None, (0, 0, 0))
    save_project(p, tmp_path / "P.rsr")
    q = open_project(tmp_path / "P.rsr")
    assert [f.copied for f in q.frames[10:]] == [False, False, True, True]
