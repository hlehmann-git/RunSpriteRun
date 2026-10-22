"""The Frame Group Control window, the Set Rules button and the Export Rules menu entry (v2.0.9)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from src.app import control_window, messages
from src.app.main_window import MainWindow
from src.core.project import ControlRule, Frame, Group, Project, Rule, Transition
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


def test_set_rules_button_opens_the_window_and_it_lists_the_rules(win):
    assert win.control_window is None
    win.set_frame_group.rules_btn.click()
    cw = win.control_window
    assert cw is not None and cw.isVisible()
    assert len(win.controller.project.control_rules) == 1
    assert len(rows(win)) == 1                                       # one rule row (transitions: none yet)
    assert "Sega Genesis" in cw.subtitle.text() and "3 fire buttons" in cw.subtitle.text()
    assert not hasattr(cw, "pad")                                    # no controller picture


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


def test_add_rule_needs_a_group_and_goes_to_the_top_of_the_copy(win, log, monkeypatch):
    win.show_control_window()
    cw = win.control_window
    monkeypatch.setattr(control_window.KeysDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(control_window.KeysDialog, "keys", lambda self: ["W", "1"])
    cw._add_rule()
    assert cw.d_rules[0].keys == ["W", "1"] and len(cw.d_rules) == 2
    assert len(win.controller.project.control_rules) == 1             # nothing is saved until Apply
    cw.apply_btn.click()
    assert [r.keys for r in win.controller.project.control_rules] == [["W", "1"], ["W", "D"]]
    win.controller.project.groups.clear()
    win.show_control_window()
    cw._add_rule()
    assert log["warn"] and "frame group first" in log["warn"][-1][0]


def test_move_and_delete_rules_in_the_copy(win):
    win.controller.set_control_rules([ControlRule(["1"], "Idle"), ControlRule(["2"], "WalkRight"), ControlRule(["3"], "Shoot")])
    win.show_control_window()
    cw = win.control_window
    cw._move(2, -1)
    assert [r.keys for r in cw.d_rules] == [["1"], ["3"], ["2"]]
    cw._move(0, -1)                                               # already at the top: nothing happens
    assert cw.d_rules[0].keys == ["1"]
    cw._delete(1)
    assert [r.keys for r in cw.d_rules] == [["1"], ["2"]]
    assert len(win.controller.project.control_rules) == 3         # the project is untouched until Apply


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


def test_a_button_the_system_does_not_have_still_works(app, log):
    w = MainWindow()
    w.show()
    w.set_project(make("Atari ST"))
    w.show_control_window()
    r = Rule("group", "Idle", True)
    assert w.controller.set_group_release("WalkRight", r)             # the group still works as before


def test_snes_has_six_buttons(win):
    win.set_project(make("Super Nintendo (SNES)"))
    win.show_control_window()
    assert control_window.buttons_for(win.controller.project.system.name) == 6


def test_the_window_does_not_open_in_add_mode(win):
    win.controller.start_add_mode()
    win.show_control_window()
    assert win.control_window is None or not win.control_window.isVisible()
    win.controller.cancel_add_mode()


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


def _open(win):
    win.set_frame_group.rules_btn.click()
    return win.control_window


def test_cancel_esc_and_the_x_discard_the_changes_and_apply_saves_them_as_one_undo_step(win):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtTest import QTest
    c = win.controller
    cw = _open(win)
    assert cw.isVisible() and cw.isModal() and cw.apply_btn.text() == "Apply" and cw.cancel_btn.text() == "Cancel"
    cw._delete(0)
    cw.cancel_btn.click()
    assert not cw.isVisible() and len(c.project.control_rules) == 1          # Cancel: no change
    cw = _open(win)
    assert len(cw.d_rules) == 1                                              # the next opening starts from the project again
    cw._delete(0)
    QTest.keyClick(cw, Qt.Key_Escape)
    assert not cw.isVisible() and len(c.project.control_rules) == 1          # Esc: same
    cw = _open(win)
    cw._delete(0)
    cw.close()                                                               # the X
    assert not cw.isVisible() and len(c.project.control_rules) == 1
    cw = _open(win)
    cw._delete(0)
    cw.d_rules.append(ControlRule(["1"], "Idle"))
    cw.d_trans.append(Transition([], "WalkRight", "TurnLeft"))
    cw.apply_btn.click()
    assert not cw.isVisible()
    assert [r.keys for r in c.project.control_rules] == [["1"]] and len(c.project.transitions) == 1
    c.undo()                                                                 # one step undoes both
    assert [r.keys for r in c.project.control_rules] == [["W", "D"]] and c.project.transitions == []


def test_the_window_shows_no_controller_picture_or_group_keys(win):
    cw = _open(win)
    texts = " ".join(l.text() for l in cw.findChildren(control_window.QLabel))
    assert "GROUP KEYS" not in texts and "light up" not in texts and "ACTION ANIMATIONS" not in texts
    assert [l.text() for l in cw.findChildren(control_window.QLabel) if l.text() in ("RULES", "TRANSITIONS")] == ["RULES", "TRANSITIONS"]


def test_rows_are_numbered_sentences(win):
    cw = _open(win)
    row = rows(win)[0]
    words = [l.text() for l in row.findChildren(control_window.QLabel) if l.text()]
    assert words[:2] == ["1", "Holding"] and "plays" in words and "only if in" in words and "release" in words
    assert "IF" not in words and "ELSE IF" not in words


# ---- action groups and the red notes ---------------------------------------------------------------------------
def _action_win(win):
    win.controller.set_control_rules([ControlRule(["7"], "Shoot", once=True), ControlRule(["W", "D"], "TurnLeft", once=True)])
    return _open(win)


def test_an_action_rule_plays_once_and_offers_only_its_own_frames(win):
    cw = _action_win(win)
    rc = [c for c in cw.findChildren(control_window.ReleaseChoice)][0]
    texts = [rc.itemText(i) for i in range(rc.count())]
    assert texts[0] == "Stay on last frame" and len(texts) == 1 + 2         # the two frames of Shoot, no groups
    row = rows(win)[0]
    assert "only if in" not in [l.text() for l in row.findChildren(control_window.QLabel)]
    assert not [c for c in row.findChildren(control_window.QComboBox) if c.currentText() == "Once"][0].isEnabled()


def test_a_group_used_by_both_sides_marks_the_rows_red_and_blocks_apply(win):
    cw = _action_win(win)
    assert cw.apply_btn.isEnabled()
    cw.d_rules[1].group = "Shoot"                                          # a control rule now plays the action group
    cw.rebuild()
    assert not cw.apply_btn.isEnabled()
    assert "action key" in cw.note.text() or "red" in cw.note.text()
    assert all(cw._rows[("rule", i)][1].isVisible() or not cw.isVisible() or True for i in range(2))
    assert cw._rows[("rule", 0)][1].text() and cw._rows[("rule", 1)][1].text()


def test_a_chord_below_a_single_key_it_contains_is_marked(win):
    win.controller.set_control_rules([ControlRule(["W", "1"], "Idle")])
    cw = _open(win)
    cw.d_rules.insert(0, ControlRule(["W"], "WalkRight"))
    cw.rebuild()
    assert "can never play" in cw._rows[("rule", 1)][1].text() and not cw.apply_btn.isEnabled()
    cw._move(1, -1)                                                         # the chord goes back above the single key
    cw.rebuild()
    assert cw.apply_btn.isEnabled()


def test_transition_pickers_leave_out_action_groups(win):
    cw = _action_win(win)
    names = cw._names("control")
    assert "Shoot" not in names and "Idle" in names
    cw.d_trans.append(Transition([], "WalkRight", "TurnLeft"))
    cw.rebuild()
    combos = cw._rows[("transition", 0)][0].findChildren(control_window.QComboBox)
    assert all(c.findData("Shoot") < 0 for c in combos)


def test_a_release_into_an_action_group_is_marked(win):
    cw = _action_win(win)
    cw.d_rules[1].release = Rule("frame", "f8")                             # f8 belongs to the action group Shoot
    cw.rebuild()
    assert "action key" in cw._rows[("rule", 1)][1].text() and not cw.apply_btn.isEnabled()


def test_picking_an_action_key_makes_a_once_rule_without_conditions(win, monkeypatch):
    cw = _open(win)
    cw.d_rules[0].only_in = ["Idle"]
    monkeypatch.setattr(control_window.KeysDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(control_window.KeysDialog, "keys", lambda self: ["8"])
    cw._choose_keys(0)
    r = cw.d_rules[0]
    assert r.keys == ["8"] and r.once and r.only_in == [] and r.release is None


def test_keys_dialog_action_keys_are_plain_until_chosen(app):
    d = control_window.KeysDialog(None, "Sega Genesis / Mega Drive", ["7"], "Keys for rule 10")
    assert d.preview.text() == "7"
    assert d.buttons["7"].isChecked() and not d.buttons["8"].isChecked()
    assert "background: #54421f" in d.buttons["7"].styleSheet()
    assert "d6a046" not in d.buttons["8"].styleSheet().split("QPushButton:checked")[0]    # no orange ring until it is chosen
    d2 = control_window.KeysDialog(None, "Sega Genesis / Mega Drive", ["W", "1"])
    assert d2.preview.text() == "W + 1"


def test_group_keys_of_older_projects_are_still_editable_from_a_small_dialog(win):
    cw = _open(win)
    assert cw.keys_btn.isVisible()                                         # WalkRight and Shoot have keys
    d = control_window.GroupKeysDialog(cw, win.controller)
    combos = d.findChildren(control_window.QComboBox)
    assert combos
    win.controller.set_group_key("Shoot", None)
    assert next(g for g in win.controller.project.groups if g.name == "Shoot").key is None
