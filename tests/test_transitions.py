"""Rick Dangerous alpha (v2.0.12): transitions, the facing list ("Only if in"), joystick-style opposite keys, and a release that plays a
group once."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QDialog

from src.app import control_window, messages
from src.app.main_window import MainWindow
from src.core import edit, groups
from src.core.project import ControlRule, Frame, Group, Project, Rule, Transition
from src.core.rules import has_opposites
from src.core.runner import Runner
from src.core.systems import get_system
from src.io import rules_export
from src.io.project_file import open_project, save_project


def make(rules=None, transitions=None):
    frames = [Frame(f"f{i + 1}", Image.new("RGB", (4, 4))) for i in range(30)]
    gs = [Group("IdleLeft", 0, 1), Group("IdleRight", 2, 3),
          Group("WalkLeft", 4, 7, key="A", on_release=Rule("frame", "f1")),
          Group("WalkRight", 8, 11, key="D", on_release=Rule("frame", "f3")),
          Group("TurnLeft", 12, 13), Group("TurnRight", 14, 15),
          Group("Settle", 16, 17, on_release=Rule("frame", "f3")),
          Group("FireLeft", 18, 19), Group("FireRight", 20, 21),
          Group("ClimbUp", 22, 24, key="W"), Group("TurnToLadder", 25, 26)]
    return Project("P", get_system("Amiga"), 4, 4, frames=frames, groups=gs, control_rules=list(rules or []),
                   transitions=list(transitions or []), dirty=False)


def run(p, frame=None):
    r = Runner(p)
    r.start()
    if frame is not None:
        r.frame = frame
    return r


def ticks(r, n=8):
    for _ in range(n):
        r.tick()


TURNS = [Transition(["WalkRight"], "WalkLeft", "TurnLeft"), Transition(["WalkLeft"], "WalkRight", "TurnRight")]


# ---- opposite keys: like a joystick --------------------------------------------------------------
def test_opposite_pairs_are_recognised():
    assert has_opposites(["A", "D"]) and has_opposites(["W", "1", "S"]) and not has_opposites(["W", "A", "1"])


def test_the_second_opposite_key_is_ignored_until_the_first_is_let_go():
    r = run(make())
    r.press("A")
    assert r.playing_group == "WalkLeft" and r.held == ["A"]
    r.press("D")                                         # D does nothing while A is held
    assert r.playing_group == "WalkLeft" and r.held == ["A"] and r.lit() == ["A"]
    r.release("A")                                       # D was held all along: it counts now, as a change from left to right
    assert r.held == ["D"] and r.playing_group == "WalkRight"
    r.release("D")
    assert r.playing_group is None and r.frame == 2      # rests on WalkRight's release frame


def test_releasing_the_ignored_key_changes_nothing():
    r = run(make())
    r.press("A")
    r.press("D")
    r.release("D")
    assert r.playing_group == "WalkLeft" and r.held == ["A"]


def test_diagonals_still_work_and_w_with_s_is_ignored():
    r = run(make([ControlRule(["W", "A"], "TurnLeft")]))
    r.press("A")
    r.press("W")
    assert r.held == ["A", "W"] and r.playing_group == "TurnLeft"
    r.press("S")
    assert r.held == ["A", "W"]


def test_a_rule_with_opposite_keys_is_refused_and_dropped_on_open(tmp_path):
    p = make()
    with pytest.raises(groups.GroupError):
        groups.check_control_rule(p, ControlRule(["A", "D"], "WalkLeft"))
    save_project(p, tmp_path / "o.rsr")
    import zipfile
    with zipfile.ZipFile(tmp_path / "o.rsr") as z:
        files = {n: z.read(n) for n in z.namelist()}
    meta = json.loads(files["project.json"])
    meta["control_rules"] = [{"keys": ["A", "D"], "group": "WalkLeft"}, {"keys": ["1"], "group": "WalkLeft"}]
    files["project.json"] = json.dumps(meta).encode()
    with zipfile.ZipFile(tmp_path / "o.rsr", "w") as z:
        for n, d in files.items():
            z.writestr(n, d)
    assert [c.keys for c in open_project(tmp_path / "o.rsr").control_rules] == [["1"]]


# ---- the facing list ("Only if in") ----------------------------------------------------------------
def fire_rules():
    left = ["IdleLeft", "WalkLeft", "TurnLeft", "FireLeft"]
    right = ["IdleRight", "WalkRight", "TurnRight", "FireRight"]
    return [ControlRule(["1"], "FireLeft", True, Rule("frame", "f1"), left), ControlRule(["1"], "FireRight", True, Rule("frame", "f3"), right)]


def test_fire_plays_the_group_for_the_way_the_character_faces():
    p = make(fire_rules())
    r = run(p, frame=5)                                  # on a WalkLeft frame
    r.press("1")
    assert r.playing_group == "FireLeft"
    r2 = run(p, frame=9)                                 # on a WalkRight frame
    r2.press("1")
    assert r2.playing_group == "FireRight"
    r3 = run(p, frame=3)                                 # resting in IdleRight
    r3.press("1")
    assert r3.playing_group == "FireRight"


def test_fire_does_nothing_when_the_frame_is_in_no_listed_group():
    r = run(make(fire_rules()), frame=22)                # a ClimbUp frame
    r.press("1")
    assert r.playing_group != "FireLeft" and r.playing_group != "FireRight"


# ---- transitions ---------------------------------------------------------------------------------
def test_turn_plays_once_then_the_walk_starts():
    r = run(make(transitions=TURNS), frame=9)            # facing right
    r.press("A")
    assert r.playing_group == "TurnLeft" and r.animating
    ticks(r, 2)
    assert r.playing_group == "WalkLeft" and r.held == ["A"]


def test_no_turn_when_already_facing_that_way_or_without_a_row():
    r = run(make(transitions=TURNS), frame=5)
    r.press("A")
    assert r.playing_group == "WalkLeft"
    r2 = run(make(), frame=9)
    r2.press("A")
    assert r2.playing_group == "WalkLeft"


def test_turn_works_after_letting_go():
    ts = [Transition(["WalkRight", "IdleRight"], "WalkLeft", "TurnLeft")]
    r = run(make(transitions=ts), frame=0)
    r.press("D")
    assert r.playing_group == "WalkRight"                # no row goes to WalkRight: straight in
    r.release("D")
    assert r.frame == 2                                  # rests on WalkRight's release frame, which is in IdleRight
    r.press("A")
    assert r.playing_group == "TurnLeft"                 # let go first, then press A: the turn still plays


def test_a_specific_row_beats_a_row_for_any_group_and_from_takes_several_groups():
    ts = [Transition([], "ClimbUp", "Settle"), Transition(["WalkRight", "WalkLeft"], "ClimbUp", "TurnToLadder")]
    r = run(make(transitions=ts), frame=9)
    r.press("W")
    assert r.playing_group == "TurnToLadder"
    r2 = run(make(transitions=ts), frame=5)
    r2.press("W")
    assert r2.playing_group == "TurnToLadder"
    r3 = run(make(transitions=ts), frame=0)              # IdleLeft: only the Any row fits
    r3.press("W")
    assert r3.playing_group == "Settle"
    ticks(r3, 2)
    assert r3.playing_group == "ClimbUp"


def test_a_start_transition_from_idle():
    ts = [Transition(["IdleRight", "IdleLeft"], "WalkRight", "Settle")]
    r = run(make(transitions=ts), frame=2)
    r.press("D")
    assert r.playing_group == "Settle"
    ticks(r, 2)
    assert r.playing_group == "WalkRight"


def test_a_transition_always_finishes_first_unless_it_can_be_interrupted():
    r = run(make(transitions=TURNS), frame=9)
    r.press("A")
    assert r.playing_group == "TurnLeft"
    r.release("A")                                       # let go mid-turn: the turn still finishes
    assert r.playing_group == "TurnLeft"
    ticks(r, 2)                                          # then it rests where it was heading: WalkLeft's release frame
    assert r.playing_group is None and r.frame == 0


def test_press_during_a_transition_is_followed_after_it():
    r = run(make(transitions=TURNS), frame=9)
    r.press("A")
    r.release("A")
    r.press("D")                                         # changed their mind mid-turn: after the turn, D's group plays
    ticks(r, 2)
    assert r.playing_group == "WalkRight"


def test_an_interruptible_transition_stops_at_once():
    ts = [Transition(["WalkRight"], "WalkLeft", "TurnLeft", interruptible=True)]
    r = run(make(transitions=ts), frame=9)
    r.press("A")
    assert r.playing_group == "TurnLeft"
    r.release("A")
    assert r.playing_group is None and r.frame == 0      # stopped: WalkLeft's release frame
    r.press("A")
    r.press("D")                                         # D is ignored while A is held
    assert r.playing_group in ("WalkLeft", "TurnLeft")


def test_interruptible_by_another_key():
    ts = [Transition(["WalkRight"], "WalkLeft", "TurnLeft", interruptible=True)]
    r = run(make(ts and None, ts), frame=9)
    r.press("A")
    assert r.playing_group == "TurnLeft"
    r.press("W")                                         # a new key: the turn stops and ClimbUp starts
    assert r.playing_group == "ClimbUp"


# ---- a release that plays a group once ---------------------------------------------------------------
def test_release_can_play_a_group_once_then_its_own_release_applies():
    p = make()
    p.groups[2].on_release = Rule("group", "Settle", False, True)        # WalkLeft releases to Settle, played once
    r = run(p)
    r.press("A")
    r.release("A")
    assert r.playing_group == "Settle" and r.animating
    ticks(r, 2)
    assert r.playing_group is None and r.frame == 2                      # Settle's own On Release: f3


def test_a_key_pressed_during_a_play_once_release_takes_over():
    p = make()
    p.groups[2].on_release = Rule("group", "Settle", False, True)
    r = run(p)
    r.press("A")
    r.release("A")
    r.press("D")
    assert r.playing_group == "WalkRight"


def test_a_group_release_with_no_loop_and_no_once_still_shows_the_first_frame_only():
    p = make()
    p.groups[2].on_release = Rule("group", "Settle", False, False)
    r = run(p)
    r.press("A")
    r.release("A")
    assert r.frame == 16 and not r.animating


# ---- file, groups, exports -----------------------------------------------------------------------------
def test_save_and_open_keep_transitions_and_play_once(tmp_path):
    p = make(fire_rules(), [Transition([], "Idle" if False else "WalkLeft", "TurnLeft", True), Transition(["WalkLeft"], "WalkRight", "TurnRight")])
    p.groups[2].on_release = Rule("group", "Settle", False, True)
    save_project(p, tmp_path / "t.rsr")
    q = open_project(tmp_path / "t.rsr")
    assert q.transitions == p.transitions and q.groups[2].on_release == Rule("group", "Settle", False, True)
    assert [(c.keys, c.group, c.once, c.only_in) for c in q.control_rules] == [(c.keys, c.group, c.once, c.only_in) for c in p.control_rules]


def test_an_older_file_with_one_from_group_becomes_a_list(tmp_path):
    p = make([ControlRule(["A"], "WalkLeft")])
    save_project(p, tmp_path / "o.rsr")
    import zipfile
    with zipfile.ZipFile(tmp_path / "o.rsr") as z:
        files = {n: z.read(n) for n in z.namelist()}
    meta = json.loads(files["project.json"])
    meta["control_rules"] = [{"keys": ["A"], "group": "WalkLeft", "once": False, "release": None, "from_group": "WalkRight"}]
    meta.pop("transitions", None)
    files["project.json"] = json.dumps(meta).encode()
    with zipfile.ZipFile(tmp_path / "o.rsr", "w") as z:
        for n, d in files.items():
            z.writestr(n, d)
    q = open_project(tmp_path / "o.rsr")
    assert q.control_rules[0].only_in == ["WalkRight"] and q.transitions == []


def test_rename_and_delete_follow_into_transitions():
    p = make(transitions=[Transition(["WalkRight", "WalkLeft"], "ClimbUp", "TurnToLadder"), Transition(["WalkLeft"], "WalkRight", "TurnRight")])
    names = {t.to for t in p.transitions} | {t.play for t in p.transitions}
    assert "TurnToLadder" in names
    pointing = groups.rules_pointing_to(p, "TurnRight")
    assert any("transition" in x for x in pointing)
    edit.delete_group(p, "TurnRight")                    # the transition that plays it goes
    assert [t.play for t in p.transitions] == ["TurnToLadder"]
    edit.delete_group(p, "WalkRight")                    # one of two from-groups goes: the row stays with the other
    assert p.transitions[0].from_groups == ["WalkLeft"]
    edit.delete_group(p, "WalkLeft")                     # no from-group left: the row goes (it must not become "any group")
    assert p.transitions == []


def test_check_transition():
    p = make()
    with pytest.raises(groups.GroupError):
        groups.check_transition(p, Transition([], "WalkLeft", "WalkLeft"))
    with pytest.raises(groups.GroupError):
        groups.check_transition(p, Transition(["Nope"], "WalkLeft", "TurnLeft"))
    groups.set_transitions(p, [Transition([], "WalkLeft", "TurnLeft")])
    assert len(p.transitions) == 1


def test_undo_restores_transitions():
    from src.core.history import restore, take
    p = make(transitions=[Transition([], "WalkLeft", "TurnLeft")])
    snap = take(p)
    p.transitions.clear()
    restore(p, snap)
    assert len(p.transitions) == 1


def test_exports_have_the_transitions_and_play_once():
    p = make(fire_rules(), [Transition(["WalkRight"], "WalkLeft", "TurnLeft", True), Transition([], "ClimbUp", "TurnToLadder")])
    p.groups[2].on_release = Rule("group", "Settle", False, True)
    d = json.loads(rules_export.rules_json(p))
    assert d["transitions"][0] == {"from": ["WalkRight"], "to": "WalkLeft", "play_first": "TurnLeft", "interruptible": True}
    assert d["transitions"][1]["from"] == "any"
    assert any(r["when_released"] == {"go_to": "group", "target": "Settle", "loop": False, "play_once": True} for r in d["rules"])
    t = rules_export.rules_text(p)
    assert "Transition from\tTo\tPlay first (once)\tCan be interrupted" in t and "Any group\tClimbUp\tTurnToLadder\tNo" in t
    assert "(play once)" in t


# ---- the window --------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app, monkeypatch):
    monkeypatch.setattr(messages, "warn", lambda *a, **k: None)
    for stray in QApplication.topLevelWidgets():
        if isinstance(stray, QDialog) and stray.isVisible():
            stray.hide()
    w = MainWindow()
    w.show()
    w.set_project(make([ControlRule(["A"], "WalkLeft")], [Transition(["WalkRight"], "WalkLeft", "TurnLeft")]))
    w.show_control_window()
    w.control_window.rebuild()
    return w


def test_the_window_lists_transitions_and_edits_them(win):
    cw = win.control_window
    assert 0 in cw._tr and cw._tr[0]["from"].text().startswith("WalkRight")
    cw._tr[0]["interruptible"].setChecked(True)
    assert win.controller.project.transitions[0].interruptible is True
    win.controller.undo()
    assert win.controller.project.transitions[0].interruptible is False
    cw.rebuild()
    cw._tr[0]["to"].setCurrentIndex(cw._tr[0]["to"].findData("ClimbUp"))
    assert win.controller.project.transitions[0].to == "ClimbUp"


def test_add_and_delete_a_transition(win):
    cw = win.control_window
    cw._add_transition()
    assert len(win.controller.project.transitions) == 2 and win.controller.project.transitions[1].from_groups == []
    cw._delete_transition(0)
    assert len(win.controller.project.transitions) == 1


def test_a_bad_transition_change_is_refused(win, monkeypatch):
    cw = win.control_window
    cw._edit_transition(0, play="WalkLeft")              # the same group as the one it goes to
    assert win.controller.project.transitions[0].play == "TurnLeft"


def test_the_keys_dialog_disables_the_opposite_key(app):
    d = control_window.KeysDialog(None, "Amiga", ["A"])
    assert not d.buttons["D"].isEnabled() and d.buttons["W"].isEnabled() and d.buttons["S"].isEnabled()
    d.buttons["A"].setChecked(False)
    assert d.buttons["D"].isEnabled()
    d.buttons["W"].setChecked(True)
    assert not d.buttons["S"].isEnabled()


def test_release_choice_has_play_once(app):
    p = make()
    rc = control_window.ReleaseChoice(p, Rule("group", "Settle", False, True), "none", lambda: None)
    assert rc.mode.currentText() == "Go to Group (play once)" and rc.rule() == Rule("group", "Settle", False, True)
    rc.mode.setCurrentIndex(2)
    assert rc.rule() == Rule("group", "Settle", True, False)
    rc.mode.setCurrentIndex(4)
    assert rc.rule() == Rule("group", "Settle", False, False)


def test_the_panels_release_editor_keeps_play_once(app):
    from src.app.rule_editor import RuleEditor
    p = make()
    ed = RuleEditor(None)
    ed.load(p, Rule("group", "Settle", False, True))
    assert ed.rule() == Rule("group", "Settle", False, True)
    ed.load(p, Rule("group", "Settle", True, False))
    assert ed.rule() == Rule("group", "Settle", True, False)


def test_renaming_a_group_follows_into_transitions_and_the_facing_list():
    p = make([ControlRule(["1"], "FireLeft", True, None, ["WalkLeft", "IdleLeft"])],
             [Transition(["WalkLeft"], "WalkRight", "TurnRight"), Transition([], "WalkLeft", "TurnLeft")])
    groups.save_group(p, "WalkLeft", "WalkLeftNew", 4, 7, "A", Rule("frame", "f1"), (0, 0, 0))
    assert p.control_rules[0].only_in == ["WalkLeftNew", "IdleLeft"]
    assert p.transitions[0].from_groups == ["WalkLeftNew"] and p.transitions[1].to == "WalkLeftNew"
