"""The Frame Group Control window, the Set Rules button and the Export Rules menu entry (v2.0.9)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from src.app import control_window, messages
from src.app.main_window import MainWindow
from src.core.project import ControlRule, Frame, Group, Project, Rule
from src.core.systems import get_system


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def log(monkeypatch):
    out = {"warn": [], "choose": []}
    monkeypatch.setattr(messages, "warn", lambda p, t, d=None: out["warn"].append((t, d)))
    monkeypatch.setattr(messages, "info", lambda p, t, d=None: None)
    monkeypatch.setattr(messages, "choose", lambda p, t, d, y, n: (out["choose"].append(t), True)[1])
    return out


def make(system="Sega Genesis / Mega Drive", rules=()):
    frames = [Frame(f"f{i + 1}", Image.new("RGB", (4, 4))) for i in range(12)]
    gs = [Group("Idle", 0, 1), Group("WalkRight", 2, 4, key="D", on_release=Rule("group", "Idle", True)),
          Group("TurnLeft", 5, 6), Group("Shoot", 7, 8, key="5")]
    return Project("P", get_system(system), 4, 4, frames=frames, groups=gs, control_rules=list(rules), dirty=False)


@pytest.fixture
def win(app, log):
    for stray in QApplication.topLevelWidgets():
        if isinstance(stray, QDialog) and stray.isVisible():
            stray.hide()
    w = MainWindow()
    w.show()
    w.set_project(make(rules=[ControlRule(["W", "D"], "TurnLeft", once=True)]))
    return w


def rows(w):
    return [w.control_window.rows.itemAt(i).widget() for i in range(w.control_window.rows.count())
            if w.control_window.rows.itemAt(i).widget() is not None and w.control_window.rows.itemAt(i).widget().objectName() == "row"]


def test_set_rules_button_opens_the_window_and_it_lists_rules_and_group_keys(win):
    assert win.control_window is None
    win.set_frame_group.rules_btn.click()
    cw = win.control_window
    assert cw is not None and cw.isVisible()
    assert len(win.controller.project.control_rules) == 1
    assert len(rows(win)) == 1 + 2                                   # one rule, then the two groups that have a key
    assert "Sega Genesis" in cw.subtitle.text() and "3 fire buttons" in cw.subtitle.text()


def test_the_panel_summary_shows_what_plays_the_group(win):
    win.set_frame_group.current = "TurnLeft"
    win.set_frame_group.blank = False
    win.set_frame_group.refresh()
    assert "W+D" in win.set_frame_group.rules_text.text() and "once" in win.set_frame_group.rules_text.text()
    win.set_frame_group.current = "WalkRight"
    win.set_frame_group.refresh()
    text = win.set_frame_group.rules_text.text()
    assert "D</b> held" in text and "On release" in text and "Idle" in text


def test_old_key_and_release_controls_are_not_shown_in_the_panel(win):
    panel = win.set_frame_group
    assert not panel.key.isVisible() and not panel.release.isVisible()
    assert panel.rules_btn.isVisible() and panel.apply_btn.isVisible()


def test_apply_keeps_the_groups_key_and_release(win):
    panel = win.set_frame_group
    panel.current, panel.blank = "WalkRight", False
    panel.refresh()
    panel.name.setText("WalkEast")
    assert panel.apply()
    g = next(g for g in win.controller.project.groups if g.name == "WalkEast")
    assert g.key == "D" and g.on_release == Rule("group", "Idle", True)


def test_changing_a_rule_is_one_undo_step(win):
    win.show_control_window()
    c = win.controller
    c.set_control_rules([ControlRule(["W", "D"], "TurnLeft", once=False)])
    assert c.project.control_rules[0].once is False
    c.undo()
    assert c.project.control_rules[0].once is True


def test_add_rule_needs_a_group_and_goes_to_the_top(win, log, monkeypatch):
    win.show_control_window()
    cw = win.control_window
    monkeypatch.setattr(control_window.KeysDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(control_window.KeysDialog, "keys", lambda self: ["W", "1"])
    cw._add_rule()
    r = win.controller.project.control_rules
    assert r[0].keys == ["W", "1"] and r[0].group == "Idle" and len(r) == 2
    win.controller.project.groups.clear()
    win.controller.frames_changed.emit()
    cw._add_rule()
    assert log["warn"] and "frame group first" in log["warn"][-1][0]


def test_move_and_delete_rules(win):
    win.show_control_window()
    cw = win.control_window
    win.controller.set_control_rules([ControlRule(["1"], "Idle"), ControlRule(["2"], "WalkRight"), ControlRule(["3"], "Shoot")])
    cw._move(2, -1)
    assert [r.keys for r in win.controller.project.control_rules] == [["1"], ["3"], ["2"]]
    cw._move(0, -1)                                               # already at the top: nothing happens
    assert win.controller.project.control_rules[0].keys == ["1"]
    cw._delete(1)
    assert [r.keys for r in win.controller.project.control_rules] == [["1"], ["2"]]


def test_group_key_and_release_are_edited_in_the_window(win, log):
    c = win.controller
    assert c.set_group_key("TurnLeft", "A")
    assert next(g for g in c.project.groups if g.name == "TurnLeft").key == "A"
    assert c.set_group_key("TurnLeft", "D")                          # D belongs to WalkRight: asked, then moved
    assert log["choose"] and next(g for g in c.project.groups if g.name == "WalkRight").key is None
    assert c.set_group_release("TurnLeft", Rule("frame", "f3"))
    assert next(g for g in c.project.groups if g.name == "TurnLeft").on_release == Rule("frame", "f3")
    c.undo()
    assert next(g for g in c.project.groups if g.name == "TurnLeft").on_release is None


def test_a_button_the_system_does_not_have_is_marked_unavailable(app, log):
    w = MainWindow()
    w.show()
    w.set_project(make("Atari ST"))                                  # one fire button; the Shoot group sits on button 5
    w.show_control_window()
    combos = [c for c in w.control_window.findChildren(control_window.QComboBox) if c.findData("5") >= 0 and c.currentData() == "5"]
    assert combos and "not on this system's controller" in combos[0].currentText()
    assert w.control_window.pad.system == "Atari ST"
    r = Rule("group", "Idle", True)
    assert w.controller.set_group_release("WalkRight", r)             # the group still works as before


def test_the_pad_lights_held_keys_and_snes_has_six_buttons(win):
    win.show_control_window()
    win.controller.keys_held.emit(["D", "W+D"])
    assert win.control_window.pad.held == {"D", "W+D"}
    win.set_project(make("Super Nintendo (SNES)"))
    win.show_control_window()
    assert control_window.buttons_for(win.controller.project.system.name) == 6


def test_window_is_off_in_add_mode_and_edit_mode(win):
    win.show_control_window()
    win.controller.start_add_mode()
    assert not win.control_window.isEnabled()
    win.controller.cancel_add_mode()
    assert win.control_window.isEnabled()


def test_export_rules_menu_writes_text_or_json(win, tmp_path, monkeypatch):
    out_txt, out_json = tmp_path / "r.txt", tmp_path / "r.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out_txt), "")))
    win.export_rules()
    assert out_txt.read_text().splitlines()[2].startswith("Priority\tSource")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out_json), "")))
    win.export_rules()
    assert json.loads(out_json.read_text())["rules"][0]["keys"] == ["W", "D"]
    assert win.act_export_rules.isEnabled() and win.act_control.isEnabled()


def test_deleting_a_group_removes_its_rule_and_the_window_follows(win):
    win.show_control_window()
    affected = win.controller.delete_group("TurnLeft")
    assert affected and win.controller.project.control_rules == []


def test_apply_esc_and_the_x_all_close_the_window(win):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtTest import QTest
    win.set_frame_group.rules_btn.click()
    cw = win.control_window
    assert cw.isVisible() and cw.apply_btn.text() == "Apply"
    QTest.keyClick(cw, Qt.Key_Escape)
    assert not cw.isVisible()                               # Esc closes it
    win.set_frame_group.rules_btn.click()
    assert cw.isVisible()
    ev = QCloseEvent()
    cw.closeEvent(ev)
    cw.hide()
    assert ev.isAccepted()                                  # the X closes it
    win.set_frame_group.rules_btn.click()
    cw.apply_btn.click()
    assert not cw.isVisible()                               # Apply closes it
    win.set_frame_group.rules_btn.click()                   # it can be opened again
    assert cw.isVisible()


def test_closing_the_main_window_closes_the_control_window(win):
    win.set_frame_group.rules_btn.click()
    assert win.control_window.isVisible()
    win.controller.project.dirty = False
    win.close()
    assert not win.control_window.isVisible()
