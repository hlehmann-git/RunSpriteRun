import pytest
from PIL import Image

from src.core.groups import (GroupError, check_group, key_owner, msg_delete_group, msg_move_key, msg_overlap,
                             msg_rules_reset, rules_pointing_to, save_group, set_start_state)
from src.core.project import Frame, Group, Project, Rule
from src.core.systems import get_system


def proj(n=10, groups=()):
    frames = [Frame(f"f{i}", Image.new("RGB", (4, 4))) for i in range(n)]
    return Project("P", get_system("Amiga"), 4, 4, frames=frames, groups=list(groups), dirty=False)


def test_messages():
    assert msg_overlap(5, 6, "Right") == "Frames 5 to 6 already belong to group Right. Groups cannot overlap."
    assert msg_move_key("W", "Walk", "Jump") == "Move key W from Walk to Jump?"
    assert msg_delete_group("Right") == "Delete group Right? Its frames stay in the timeline."
    assert msg_rules_reset("Jump", ["group Idle (On Release)", "Start state"]) == \
        "These rules pointed to Jump and have been reset: group Idle (On Release), Start state."


def test_check_group_rules():
    p = proj(groups=[Group("Idle", 0, 1), Group("Right", 4, 7)])
    check_group(p, None, "Jump", 8, 9)
    check_group(p, "Right", "Right", 3, 7)                      # editing may keep its own frames
    with pytest.raises(GroupError, match="no spaces"):
        check_group(p, None, "bad name", 2, 3)
    with pytest.raises(GroupError, match="already exists"):
        check_group(p, None, "right", 2, 3)
    with pytest.raises(GroupError, match="From must not be after To"):
        check_group(p, None, "X", 3, 2)
    with pytest.raises(GroupError) as e:
        check_group(p, None, "X", 6, 9)
    assert str(e.value) == "Frames 7 to 8 already belong to group Right. Groups cannot overlap."
    with pytest.raises(GroupError, match="Idle"):
        check_group(p, "Right", "Right", 1, 5)


def test_limit_32():
    p = proj(n=40, groups=[Group(f"G{i}", i, i) for i in range(32)])
    with pytest.raises(GroupError, match="up to 32"):
        check_group(p, None, "More", 33, 33)
    check_group(p, "G0", "G0", 0, 0)                            # editing is still fine


def test_save_new_group_sorted_and_dirty():
    p = proj(groups=[Group("Right", 4, 7)])
    save_group(p, None, "Idle", 0, 1, "S", Rule("frame", "f0"), (255, 0, 0))
    assert [g.name for g in p.groups] == ["Idle", "Right"] and p.dirty
    assert p.groups[0].key == "S" and p.groups[0].colour == (255, 0, 0)


def test_key_reassigned_from_other_group():
    p = proj(groups=[Group("Walk", 0, 1, key="W")])
    assert key_owner(p, "W") == "Walk" and key_owner(p, "W", ignore="Walk") is None and key_owner(p, None) is None
    save_group(p, None, "Jump", 3, 4, "W", None, (0, 0, 0))
    assert [(g.name, g.key) for g in p.groups] == [("Walk", None), ("Jump", "W")]


def test_rename_updates_rules_and_edit_values():
    p = proj(groups=[Group("A", 0, 1, on_release=Rule("group", "A", True)), Group("B", 3, 4, on_release=Rule("group", "A"))])
    set_start_state(p, Rule("group", "A", True))
    save_group(p, "A", "Idle", 0, 2, "D", Rule("group", "Idle", True), (1, 2, 3))
    assert [g.name for g in p.groups] == ["Idle", "B"] and (p.groups[0].first, p.groups[0].last) == (0, 2)
    assert p.groups[1].on_release.target == "Idle" and p.start_state.target == "Idle"


def test_rules_pointing_to():
    p = proj(groups=[Group("A", 0, 1), Group("B", 3, 4, on_release=Rule("group", "A")), Group("C", 6, 7, on_release=Rule("frame", "f0"))])
    set_start_state(p, Rule("group", "A"))
    assert rules_pointing_to(p, "A") == ["group B (On Release)", "Start state"]
    assert rules_pointing_to(p, "C") == []
