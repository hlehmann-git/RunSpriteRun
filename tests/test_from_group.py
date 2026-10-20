"""The "Only after" condition on a Frame Group Control rule (v2.0.10): a turn that plays only when the
character is facing the other way."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QDialog

from src.app import messages
from src.app.main_window import MainWindow
from src.core import edit, groups
from src.core.project import ControlRule, Frame, Group, Project, Rule
from src.core.runner import Runner
from src.core.systems import get_system
from src.io import rules_export
from src.io.project_file import open_project, save_project


def make(rules=None):
    frames = [Frame(f"f{i + 1}", Image.new("RGB", (4, 4))) for i in range(16)]
    gs = [Group("WalkLeft", 0, 2, on_release=Rule("frame", "f2")), Group("TurnLeft", 3, 4),
          Group("WalkRight", 5, 7, on_release=Rule("frame", "f7")), Group("TurnRight", 8, 9)]
    if rules is None:
        rules = [ControlRule(["A"], "TurnLeft", True, None, "WalkRight"), ControlRule(["A"], "WalkLeft"),
                 ControlRule(["D"], "TurnRight", True, None, "WalkLeft"), ControlRule(["D"], "WalkRight")]
    return Project("P", get_system("Amiga"), 4, 4, frames=frames, groups=gs, control_rules=rules, dirty=False)


def run(p, start_frame=None):
    r = Runner(p)
    r.start()
    if start_frame is not None:
        r.frame = start_frame
    return r


def play_out(r, n=6):
    for _ in range(n):
        r.tick()


def test_turn_plays_once_only_when_facing_the_other_way_then_walks():
    r = run(make(), start_frame=6)                      # resting on a WalkRight frame
    r.press("A")
    assert r.playing_group == "TurnLeft"
    play_out(r)
    assert r.playing_group == "WalkLeft"                # the turn is done: the walk takes over (no second turn)
    r.tick()
    assert r.playing_group == "WalkLeft" and r.held == ["A"]


def test_no_turn_when_already_facing_that_way():
    r = run(make(), start_frame=1)                      # resting on a WalkLeft frame
    r.press("A")
    assert r.playing_group == "WalkLeft"


def test_turn_works_after_letting_go_and_waiting_and_with_the_other_key_still_held():
    r = run(make(), start_frame=0)
    r.press("D")
    assert r.playing_group == "TurnRight"
    play_out(r)
    assert r.playing_group == "WalkRight"
    r.release("D")
    assert r.frame == 6                                 # rests on a WalkRight frame
    r.press("A")                                        # let go first, then press A: the turn still fires
    assert r.playing_group == "TurnLeft"
    play_out(r)
    r.release("A")
    r.press("D")
    assert r.playing_group == "TurnRight"


def test_the_turn_is_not_interrupted_by_another_key_while_it_plays():
    r = run(make(), start_frame=6)
    r.press("A")
    r.tick()
    assert r.playing_group == "TurnLeft"
    r.press("W")                                        # a key no rule uses does nothing
    assert r.playing_group == "TurnLeft"


def test_rename_delete_and_check_follow_the_condition():
    p = make()
    groups.set_control_rules(p, p.control_rules)
    bad = ControlRule(["A"], "WalkLeft", False, None, "Nope")
    with pytest.raises(groups.GroupError):
        groups.check_control_rule(p, bad)
    assert any("Only after" in x or "Frame Group Control" in x for x in groups.rules_pointing_to(p, "WalkRight"))
    edit.delete_group(p, "WalkRight")
    assert all(r.from_group != "WalkRight" and r.group != "WalkRight" for r in p.control_rules)
    assert len(p.control_rules) == 2                    # the turn that needed WalkRight and the rule that plays it went with it


def test_save_open_and_export_keep_the_condition(tmp_path):
    p = make()
    save_project(p, tmp_path / "x.rsr")
    back = open_project(tmp_path / "x.rsr")
    assert [r.from_group for r in back.control_rules] == ["WalkRight", "", "WalkLeft", ""]
    rows = rules_export.rule_rows(p)
    assert rows[0]["only_after"] == "WalkRight" and rows[1]["only_after"] is None
    data = json.loads(rules_export.rules_json(p))
    assert data["rules"][0]["only_after"] == "WalkRight"
    lines = rules_export.rules_text(p).splitlines()
    assert "Only after" in lines[2] and lines[3].split("\t")[3] == "WalkRight"


def test_an_old_file_has_no_condition(tmp_path):
    p = make([ControlRule(["A"], "WalkLeft")])
    save_project(p, tmp_path / "o.rsr")
    assert open_project(tmp_path / "o.rsr").control_rules[0].from_group == ""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_the_window_has_the_drop_down_and_a_change_is_applied(app, monkeypatch):
    monkeypatch.setattr(messages, "warn", lambda *a, **k: None)
    for stray in QApplication.topLevelWidgets():
        if isinstance(stray, QDialog) and stray.isVisible():
            stray.hide()
    w = MainWindow()
    w.show()
    w.set_project(make())
    w.show_control_window()
    win = w.control_window
    win.rebuild()
    box = win._from[0]
    assert box.currentData() == "WalkRight" and win._from[1].currentData() == ""
    box.setCurrentIndex(box.findData("WalkLeft"))
    assert w.controller.project.control_rules[0].from_group == "WalkLeft"
    w.controller.undo()
    assert w.controller.project.control_rules[0].from_group == "WalkRight"
