"""Action animations (7 8 9 0), the cross-layout Keys held window, Shorten Frame Names."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.app.control_window import KeysDialog
from src.core import edit, groups
from src.core.project import ControlRule, Frame, Group, Project, Rule
from src.core.runner import Runner
from src.core.rules import ACTION_KEYS, KEYS, key_available, keys_text
from src.core.systems import get_system

app = QApplication.instance() or QApplication([])


def make(n=8, labels=None):
    frames = [Frame((labels or [f"f_{i + 1:03d}" for i in range(n)])[i], Image.new("RGB", (4, 4))) for i in range(n)]
    gs = [Group("Walk", 0, 2), Group("Die", 3, 5), Group("Idle", 6, 7)]
    return Project("P", get_system("Amiga"), 4, 4, frames=frames, groups=gs, dirty=False)


def test_action_keys_exist_on_every_system():
    assert ACTION_KEYS == ("7", "8", "9", "0") and all(k in KEYS for k in ACTION_KEYS)
    for system in ("Amiga", "Sega Genesis / Mega Drive", "Super Nintendo (SNES)"):
        assert all(key_available(system, k) for k in ACTION_KEYS)
    assert keys_text(["0", "W", "7"]) == "W+7+0"


def test_an_action_key_rule_must_stand_alone():
    p = make()
    groups.check_control_rule(p, ControlRule(["7"], "Die", True))
    for keys in (["7", "W"], ["8", "1"], ["7", "8"]):
        with pytest.raises(groups.GroupError):
            groups.check_control_rule(p, ControlRule(keys, "Die", True))


def test_an_action_key_plays_its_group_and_nothing_else_counts_while_it_is_held():
    p = make()
    p.control_rules = [ControlRule(["D"], "Walk", False), ControlRule(["7"], "Die", True, Rule("frame", "f_007"))]
    r = Runner(p)
    r.start()
    r.press("D")
    assert r.playing_group == "Walk"
    r.press("7")
    assert r.held == ["7"] and r.playing_group == "Die"      # D is ignored while the action key is down
    r.release("7")
    assert r.held == ["D"]                                    # D counts again once 7 is let go


def test_keys_window_has_a_cross_diagonals_and_a_lone_action_row():
    d = KeysDialog(None, "Super Nintendo (SNES)", ["W", "D"])
    assert d.keys() == ["W", "D"] and d.corners["W+D"].isChecked()
    assert not d.buttons["A"].isEnabled() and not d.buttons["S"].isEnabled()      # opposites are not available
    assert not d.corners["S+A"].isEnabled()
    d.corners["W+D"].setChecked(False)                                         # a corner lets go of both its keys
    assert d.keys() == []
    d.corners["W+A"].setChecked(True)
    assert d.keys() == ["W", "A"]
    d.buttons["7"].setChecked(True)                                           # an action key stands alone
    assert d.keys() == ["7"]
    assert not d.buttons["W"].isEnabled() and not d.buttons["1"].isEnabled() and d.buttons["8"].isEnabled() is False
    d.buttons["7"].setChecked(False)
    d.buttons["W"].setChecked(True)
    assert d.keys() == ["W"] and d.buttons["7"].isEnabled()


def test_shared_text_is_swapped_and_numbers_stay():
    p = make(3, ["Rick_SpriteSheet_Amiga_001", "Rick_SpriteSheet_Amiga_002", "Rick_SpriteSheet_Amiga_003"])
    assert edit.shared_prefix(p) == "Rick_SpriteSheet_Amiga"
    p.groups[0].on_release = Rule("frame", "Rick_SpriteSheet_Amiga_003")
    assert edit.shorten_names(p, "Rick")
    assert [f.label for f in p.frames] == ["Rick_001", "Rick_002", "Rick_003"]
    assert p.groups[0].on_release.target == "Rick_003"                         # rules follow the new labels


def test_only_whole_parts_are_shared_when_names_differ():
    p = make(3, ["Rick_walk_001", "Rick_jump_002", "Rick_walkB_003"])
    assert edit.shared_prefix(p) == "Rick"
    edit.shorten_names(p, "R")
    assert [f.label for f in p.frames] == ["R_walk_001", "R_jump_002", "R_walkB_003"]
    q = make(2, ["walk1_001", "walk2_002"])
    assert edit.shared_prefix(q) == ""


def test_shorten_refuses_empty_bad_or_unshared():
    p = make(2, ["Rick_a_001", "Rick_b_002"])
    for bad in ("", "has space"):
        with pytest.raises(edit.EditError):
            edit.shorten_names(p, bad)
    q = make(2, ["x_001", "y_002"])
    with pytest.raises(edit.EditError):
        edit.shorten_names(q, "Rick")


def test_edit_menu_has_shorten_frame_names_and_it_works():
    from src.app import messages
    from src.app.main_window import MainWindow
    w = MainWindow()
    w.show()
    p = make(3, ["Rick_SpriteSheet_001", "Rick_SpriteSheet_002", "Rick_SpriteSheet_003"])
    w.set_project(p)
    assert w.act_shorten in w.menu_edit.actions() and w.act_shorten.isEnabled()
    from src.app import shorten_dialog
    shorten_dialog.ShortenDialog.exec = lambda self: (self.name.setText("Rick") or True)
    messages.choose = lambda *a, **k: True
    w.act_shorten.trigger()
    assert [f.label for f in w.controller.project.frames] == ["Rick_001", "Rick_002", "Rick_003"]
    assert not w.controller.can_undo                                            # it cannot be undone
