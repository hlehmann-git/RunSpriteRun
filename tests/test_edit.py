import pytest
from PIL import Image

from src.core.edit import EditError, delete_group, group_of_frame, move_frame, rename_label
from src.core.project import Frame, Group, Project, Rule
from src.core.systems import get_system


def make_project(n=6, groups=()):
    frames = [Frame(f"f{i}", Image.new("RGB", (4, 4), (0, 0, 0))) for i in range(n)]
    return Project("P", get_system("Amiga"), 4, 4, frames=frames, groups=list(groups), dirty=False)


def labels(p):
    return [f.label for f in p.frames]


def test_rename_ok_and_rules_follow():
    p = make_project(groups=[Group("G", 0, 1, on_release=Rule("frame", "f2"))])
    p.start_state = Rule("frame", "f2")
    assert rename_label(p, 2, "Jump_1") is True
    assert p.frames[2].label == "Jump_1"
    assert p.groups[0].on_release.target == "Jump_1" and p.start_state.target == "Jump_1" and p.dirty
    assert rename_label(p, 2, "Jump_1") is False


def test_rename_refused():
    p = make_project()
    with pytest.raises(EditError, match="no spaces"):
        rename_label(p, 0, "bad name")
    with pytest.raises(EditError, match="unique"):
        rename_label(p, 0, "F1")                     # same as f1, case-insensitive
    assert p.frames[0].label == "f0" and not p.dirty


def test_move_without_groups():
    p = make_project()
    assert move_frame(p, 0, 2) and labels(p) == ["f1", "f2", "f0", "f3", "f4", "f5"] and p.dirty
    assert not move_frame(p, 3, 3)


def test_move_in_and_out_of_groups():
    p = make_project(groups=[Group("A", 1, 3)])          # frames f1 f2 f3
    # drop f5 between two frames of A: joins A
    move_frame(p, 5, 2)
    assert group_of_frame(p) == [None, "A", "A", "A", "A", None] and (p.groups[0].first, p.groups[0].last) == (1, 4)
    # drop next to the end of A, outside it: does not join
    p = make_project(groups=[Group("A", 1, 3)])
    move_frame(p, 5, 4)
    assert group_of_frame(p) == [None, "A", "A", "A", None, None]
    # move a member out of the group: leaves it
    p = make_project(groups=[Group("A", 1, 3)])
    move_frame(p, 2, 5)
    assert group_of_frame(p) == [None, "A", "A", None, None, None] and (p.groups[0].first, p.groups[0].last) == (1, 2)


def test_move_inside_group_stays():
    p = make_project(groups=[Group("A", 0, 3)])
    move_frame(p, 0, 2)
    assert group_of_frame(p)[:4] == ["A"] * 4


def test_move_to_either_end_of_own_group_stays_but_one_step_out_leaves():
    for src, dst in ((1, 3), (3, 1)):                           # group A is frames 1, 2, 3
        p = make_project(groups=[Group("A", 1, 3)])
        move_frame(p, src, dst)
        assert group_of_frame(p) == [None, "A", "A", "A", None, None]
    p = make_project(groups=[Group("A", 1, 3)])
    move_frame(p, 3, 4)                                         # swap with the frame after the group
    assert group_of_frame(p) == [None, "A", "A", None, None, None]
    p = make_project(groups=[Group("A", 1, 3)])
    move_frame(p, 1, 0)                                         # swap with the frame before the group
    assert group_of_frame(p) == [None, None, "A", "A", None, None]
    p = make_project(groups=[Group("A", 1, 2)])                 # two-frame group: swap its frames
    move_frame(p, 1, 2)
    assert group_of_frame(p) == [None, "A", "A", None, None, None]


def test_group_losing_last_frame_needs_confirmation():
    p = make_project(groups=[Group("Solo", 2, 2, on_release=Rule("group", "Solo"))])
    p.groups.append(Group("Other", 4, 5, on_release=Rule("group", "Solo")))
    asked = []
    assert move_frame(p, 2, 0, lambda names: (asked.append(names), False)[1]) is False
    assert asked == [["Solo"]] and labels(p)[0] == "f0" and len(p.groups) == 2 and not p.dirty
    assert move_frame(p, 2, 0, lambda names: True) is True
    assert [g.name for g in p.groups] == ["Other"] and p.groups[0].on_release is None and p.frames[0].label == "f2"


def test_delete_group_resets_rules():
    p = make_project(groups=[Group("A", 0, 1), Group("B", 2, 3, on_release=Rule("group", "A"))])
    p.start_state = Rule("group", "A")
    assert delete_group(p, "A") == ["group B (On Release)", "Start state"]
    assert [g.name for g in p.groups] == ["B"] and p.groups[0].on_release is None and p.start_state is None


# ---- Timeline copy / paste (clone_frame) ----
def numbered(n=5, first=1, groups=None):
    frames = [Frame(f"Idle_{i}", Image.new("RGB", (4, 4), (i, 0, 0))) for i in range(first, first + n)]
    return Project("P", get_system("Amiga"), 4, 4, frames=frames, groups=groups if groups is not None else [Group("Idle", 0, n - 1)], dirty=False)


def test_clone_after_renumbers_the_group():
    from src.core.edit import clone_frame
    p = numbered()
    p.groups[0].on_release = Rule("frame", "Idle_4")
    src = Frame("Idle_1", p.frames[0].image)
    idx = clone_frame(p, src, 2, True)                       # after Idle_3
    assert idx == 3 and labels(p) == ["Idle_1", "Idle_2", "Idle_3", "Idle_4", "Idle_5", "Idle_6"]
    assert p.frames[3].image is src.image and (p.groups[0].first, p.groups[0].last) == (0, 5)
    assert p.groups[0].on_release.target == "Idle_5" and p.dirty


def test_clone_before_renumbers_from_the_selected_frame():
    from src.core.edit import clone_frame
    p = numbered()
    idx = clone_frame(p, Frame("Idle_5", p.frames[4].image), 1, False)      # before Idle_2
    assert idx == 1 and labels(p) == ["Idle_1", "Idle_2", "Idle_3", "Idle_4", "Idle_5", "Idle_6"]


def test_clone_outside_a_group_gets_001():
    from src.core.edit import clone_frame
    p = make_project()
    idx = clone_frame(p, Frame("f2", p.frames[2].image), 4, True)
    assert idx == 5 and p.frames[5].label == "f2_001" and len(p.frames) == 7
    idx = clone_frame(p, Frame("f2", p.frames[2].image), 4, True)
    assert p.frames[5].label == "f2_002" and labels(p).count("f2_001") == 1


def test_clone_follows_the_group_it_lands_in():
    from src.core.edit import clone_frame
    p = numbered(3)
    p.frames.append(Frame("Jump", Image.new("RGB", (4, 4))))
    clone_frame(p, Frame("Jump", p.frames[3].image), 2, True)         # a Jump copy after Idle_3 becomes Idle_4
    assert labels(p) == ["Idle_1", "Idle_2", "Idle_3", "Idle_4", "Jump"] and p.groups[0].last == 3


def test_clone_stops_at_120_frames():
    from src.core.edit import clone_frame
    p = make_project(120)
    with pytest.raises(EditError, match="at most 120"):
        clone_frame(p, p.frames[0], 0, True)
    assert len(p.frames) == 120
