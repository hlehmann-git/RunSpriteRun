"""Frame Group Control rules (v2.0.9): keys held play a group, play-once, priority, release, edits and the file."""
import json
import zipfile

import pytest
from PIL import Image

from src.core import edit, groups
from src.core.history import restore, take
from src.core.project import ControlRule, Frame, Group, Project, Rule
from src.core.rules import buttons_for, key_available, keys_for, keys_text
from src.core.runner import Runner
from src.core.systems import get_system
from src.io.project_file import open_project, save_project


def make(rules, system="Sega Genesis / Mega Drive"):
    frames = [Frame(f"f{i + 1}", Image.new("RGB", (4, 4))) for i in range(20)]
    gs = [Group("Idle", 0, 1), Group("WalkRight", 2, 4, key="D", on_release=Rule("group", "Idle", True)),
          Group("WalkLeft", 5, 7, key="A", on_release=Rule("frame", "f1")), Group("TurnLeft", 8, 9),
          Group("ShootUpRight", 10, 12), Group("WalkUpRight", 13, 15, key="W+D")]
    return Project("P", get_system(system), 4, 4, frames=frames, groups=gs, control_rules=rules, dirty=False)


def run(p):
    r = Runner(p)
    r.start()
    return r


def test_buttons_per_system():
    assert buttons_for("Atari ST") == 1 and buttons_for("Amiga") == 1 and buttons_for("Commodore 64") == 1
    assert buttons_for("Sega Genesis / Mega Drive") == 3 and buttons_for("Super Nintendo (SNES)") == 6
    assert keys_for("Atari ST") == ("W", "A", "S", "D", "1")
    assert key_available("Atari ST", "4") is False and key_available("Super Nintendo (SNES)", "6") is True
    assert key_available("Atari ST", "W+D") is True and key_available("Atari ST", None) is True
    assert keys_text(["1", "D", "W"]) == "W+D+1"


def test_chord_rule_wins_over_the_basic_key_and_returns_when_the_extra_key_is_let_go():
    p = make([ControlRule(["W", "D", "1"], "ShootUpRight")])
    r = run(p)
    r.press("D")
    assert r.playing_group == "WalkRight"
    r.press("W")
    assert r.playing_group == "WalkUpRight"                  # W+D, its own basic group
    r.press("1")
    assert r.playing_group == "ShootUpRight"                 # W+D then adding button 1: W+D becomes W+D+1
    r.release("1")
    assert r.playing_group == "WalkUpRight"                  # back to W+D


def test_play_once_rule_plays_through_then_the_newest_key_takes_over():
    p = make([ControlRule(["D", "A"], "TurnLeft", once=True)])
    r = run(p)
    r.press("D")
    r.press("A")                                             # D then A: D&A
    assert r.playing_group == "TurnLeft" and r.animating
    seen = [r.frame]
    for _ in range(3):
        r.tick()
        seen.append(r.frame)
    assert seen[:2] == [8, 9]                                # the turn plays once ...
    assert r.playing_group == "WalkLeft"                     # ... then A (the newest key) walks left
    r.release("D")
    assert r.playing_group == "WalkLeft"


def test_play_once_does_not_fire_again_until_the_keys_are_let_go():
    p = make([ControlRule(["1"], "ShootUpRight", once=True)])
    r = run(p)
    r.press("1")
    for _ in range(5):
        r.tick()
    assert r.playing_group is None and r.frame == 12         # finished: group's last frame (no On Release set)
    r.release("1")
    r.press("1")
    assert r.playing_group == "ShootUpRight"                 # pressed again: it fires again


def test_rule_release_choice_beats_the_groups_on_release():
    p = make([ControlRule(["1"], "WalkRight", release=Rule("frame", "f15"))])
    r = run(p)
    r.press("1")
    assert r.playing_group == "WalkRight"
    r.release("1")
    assert r.frame == 14                                     # the rule's own Go To Frame, not WalkRight's Idle loop


def test_rule_without_release_uses_the_groups_on_release():
    p = make([ControlRule(["1"], "WalkRight")])
    r = run(p)
    r.press("1")
    r.release("1")
    assert r.playing_group == "Idle"


def test_rules_are_checked_from_the_top():
    p = make([ControlRule(["D"], "WalkLeft"), ControlRule(["W", "D"], "ShootUpRight")])
    r = run(p)
    r.press("W")
    r.press("D")
    assert r.playing_group == "WalkLeft"                     # the top rule matches first
    p.control_rules.reverse()
    r.stop()
    r.start()
    r.press("W")
    r.press("D")
    assert r.playing_group == "ShootUpRight"


def test_a_key_used_only_by_a_rule_counts_and_is_lit():
    p = make([ControlRule(["2"], "ShootUpRight")])
    r = run(p)
    assert r.press("2") and "2" in r.lit()
    assert r.press("3") is False                             # no group and no rule uses 3


def test_rule_for_a_missing_group_is_ignored():
    p = make([ControlRule(["1"], "Gone")])
    r = run(p)
    assert r.press("1") is True and r.playing_group is None


def test_deleting_a_group_removes_its_rules_and_clears_release_targets():
    p = make([ControlRule(["1"], "ShootUpRight"), ControlRule(["2"], "WalkLeft", release=Rule("group", "ShootUpRight", True))])
    affected = groups.rules_pointing_to(p, "ShootUpRight")
    assert any("1" in a for a in affected) and len(affected) == 2
    edit.delete_group(p, "ShootUpRight")
    assert [c.keys for c in p.control_rules] == [["2"]] and p.control_rules[0].release is None


def test_renaming_a_group_follows_into_rules():
    p = make([ControlRule(["1"], "WalkRight", release=Rule("group", "WalkRight", True))])
    groups.save_group(p, "WalkRight", "WalkEast", 2, 4, "D", Rule("group", "Idle", True), (0, 0, 0))
    assert p.control_rules[0].group == "WalkEast" and p.control_rules[0].release.target == "WalkEast"


def test_deleting_frames_that_empty_a_group_removes_its_rules():
    p = make([ControlRule(["1"], "TurnLeft"), ControlRule(["2"], "Idle", release=Rule("frame", "f9"))])
    plan = edit.plan_delete(p, [8, 9])
    assert plan.emptied == ["TurnLeft"] and any("rule 1" in x for x in plan.resets)
    edit.delete_frames(p, [8, 9])
    assert [c.keys for c in p.control_rules] == [["2"]]


def test_check_rule_and_set_rules():
    p = make([])
    with pytest.raises(groups.GroupError):
        groups.set_control_rules(p, [ControlRule([], "Idle")])
    with pytest.raises(groups.GroupError):
        groups.set_control_rules(p, [ControlRule(["Q"], "Idle")])
    with pytest.raises(groups.GroupError):
        groups.set_control_rules(p, [ControlRule(["1"], "Nope")])
    groups.set_control_rules(p, [ControlRule(["1"], "Idle")])
    assert p.dirty and len(p.control_rules) == 1


def test_undo_snapshot_holds_the_rules():
    p = make([ControlRule(["1"], "Idle")])
    snap = take(p)
    p.control_rules.append(ControlRule(["2"], "Idle"))
    assert not snap.same_as(take(p))
    restore(p, snap)
    assert len(p.control_rules) == 1


def test_save_and_open_keeps_the_rules(tmp_path):
    p = make([ControlRule(["W", "D", "1"], "ShootUpRight", once=True, release=Rule("group", "Idle", True)),
              ControlRule(["2"], "WalkLeft")])
    f = tmp_path / "P.rsr"
    save_project(p, f)
    q = open_project(f)
    assert q.control_rules == p.control_rules


def test_older_file_without_rules_opens_and_bad_rules_are_dropped(tmp_path):
    p = make([ControlRule(["1"], "Idle")])
    f = tmp_path / "P.rsr"
    save_project(p, f)
    with zipfile.ZipFile(f) as z:
        files = {n: z.read(n) for n in z.namelist()}
    meta = json.loads(files["project.json"])
    meta["control_rules"] = [{"keys": ["1"], "group": "Idle"}, {"keys": ["Q"], "group": "Idle"},
                             {"keys": ["2"], "group": "Gone"}, "junk"]
    files["project.json"] = json.dumps(meta).encode()
    with zipfile.ZipFile(f, "w") as z:
        for n, d in files.items():
            z.writestr(n, d)
    assert [c.keys for c in open_project(f).control_rules] == [["1"]]
    del meta["control_rules"]
    files["project.json"] = json.dumps(meta).encode()
    with zipfile.ZipFile(f, "w") as z:
        for n, d in files.items():
            z.writestr(n, d)
    assert open_project(f).control_rules == []
