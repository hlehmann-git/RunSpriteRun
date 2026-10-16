import pytest
from PIL import Image

from src.core.edit import EditError, convert_old_labels, delete_group, group_of_frame, move_frame, rename_label, renumber
from src.core.project import Frame, Group, Project, Rule
from src.core.systems import get_system


def make_project(n=6, groups=()):
    frames = [Frame(f"f{i}_{i + 1:03d}", Image.new("RGB", (4, 4), (0, 0, 0))) for i in range(n)]
    return Project("P", get_system("Amiga"), 4, 4, frames=frames, groups=list(groups), dirty=False)


def labels(p):
    return [f.label for f in p.frames]


def test_rename_ok_and_rules_follow():
    p = make_project(groups=[Group("G", 0, 1, on_release=Rule("frame", "f2_003"))])
    p.start_state = Rule("frame", "f2_003")
    assert rename_label(p, 2, "Jump_1") is True
    assert p.frames[2].label == "Jump_1_003"                      # the number stays the position and cannot be changed
    assert p.groups[0].on_release.target == "Jump_1_003" and p.start_state.target == "Jump_1_003" and p.dirty
    assert rename_label(p, 2, "Jump_1") is False


def test_rename_refused():
    p = make_project()
    with pytest.raises(EditError, match="no spaces"):
        rename_label(p, 0, "bad name")
    with pytest.raises(EditError, match="needs a name"):
        rename_label(p, 0, "")
    with pytest.raises(EditError, match="no spaces"):
        rename_label(p, 0, "x" * 61 + " ")
    assert p.frames[0].label == "f0_001" and not p.dirty


def test_names_can_repeat_and_end_in_digits():
    p = make_project()
    assert rename_label(p, 1, "f0") and p.frames[1].label == "f0_002"        # same name as frame 1: fine, numbers differ
    assert rename_label(p, 3, "4534") and p.frames[3].label == "4534_004"
    assert rename_label(p, 4, "Idle_4") and p.frames[4].label == "Idle_4_005"
    assert rename_label(p, 5, "n" * 60) and len(p.frames[5].label) == 64


def test_renaming_a_frame_in_a_group_renames_the_whole_group():
    p = make_project(groups=[Group("G", 1, 3, on_release=Rule("frame", "f2_003"))])
    p.start_state = Rule("frame", "f1_002")
    assert rename_label(p, 2, "Walk") is True
    assert labels(p) == ["f0_001", "Walk_002", "Walk_003", "Walk_004", "f4_005", "f5_006"]
    assert p.groups[0].on_release.target == "Walk_003" and p.start_state.target == "Walk_002"
    assert rename_label(p, 0, "Solo") and labels(p)[0] == "Solo_001" and labels(p)[1] == "Walk_002"     # outside a group: only itself


def test_move_without_groups():
    p = make_project()
    assert move_frame(p, 0, 2) and labels(p) == ["f1_001", "f2_002", "f0_003", "f3_004", "f4_005", "f5_006"] and p.dirty
    assert not move_frame(p, 3, 3)


def test_move_renumbers_and_rules_follow_the_frame():
    p = make_project(groups=[Group("G", 0, 0, on_release=Rule("frame", "f4_005"))])
    p.start_state = Rule("frame", "f2_003")
    move_frame(p, 4, 1)
    assert labels(p) == ["f0_001", "f4_002", "f1_003", "f2_004", "f3_005", "f5_006"]
    assert p.groups[0].on_release.target == "f4_002" and p.start_state.target == "f2_004"


def test_renumber_sets_numbers_and_keeps_names():
    p = make_project(3)
    p.frames[1].label = "Mid_900"
    p.frames[2].label = "x"
    assert renumber(p) and labels(p) == ["f0_001", "Mid_002", "x_003"]
    assert not renumber(p)


def test_old_project_labels_are_converted():
    p = make_project(7, groups=[Group("G", 5, 5, on_release=Rule("frame", "Idle_4"))])
    p.frames[5].label = "Idle_4"
    p.frames[6].label = "Run"
    p.frames[0].label = "_9"
    p.frames[1].label = "Idle_004_001"
    p.frames[2].label = "007"
    p.frames[0].copied = True
    convert_old_labels(p)
    assert labels(p) == ["Frame_001", "Idle_004_002", "007_003", "f3_004", "f4_005", "Idle_006", "Run_007"]
    assert p.groups[0].on_release.target == "Idle_006" and not p.frames[0].copied and not p.dirty


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
    assert asked == [["Solo"]] and labels(p)[0] == "f0_001" and len(p.groups) == 2 and not p.dirty
    assert move_frame(p, 2, 0, lambda names: True) is True
    assert [g.name for g in p.groups] == ["Other"] and p.groups[0].on_release is None and p.frames[0].label == "f2_001"


def test_delete_group_resets_rules():
    p = make_project(groups=[Group("A", 0, 1), Group("B", 2, 3, on_release=Rule("group", "A"))])
    p.start_state = Rule("group", "A")
    assert delete_group(p, "A") == ["group B (On Release)", "Start state"]
    assert [g.name for g in p.groups] == ["B"] and p.groups[0].on_release is None and p.start_state is None


# ---- Timeline copy / paste (clone_frame) ----
def numbered(n=5, first=1, groups=None):
    frames = [Frame(f"Idle_{i - first + 1:03d}", Image.new("RGB", (4, 4), (i, 0, 0))) for i in range(first, first + n)]
    return Project("P", get_system("Amiga"), 4, 4, frames=frames, groups=groups if groups is not None else [Group("Idle", 0, n - 1)], dirty=False)


def test_clone_after_keeps_name_takes_position_and_stays_in_the_group():
    from src.core.edit import clone_frame
    p = numbered()
    p.groups[0].on_release = Rule("frame", "Idle_004")
    src = Frame("Idle_003", p.frames[2].image)
    idx = clone_frame(p, src, 2, True)                       # after frame 3
    assert idx == 3 and labels(p) == ["Idle_001", "Idle_002", "Idle_003", "Idle_004", "Idle_005", "Idle_006"]
    assert p.frames[3].image is src.image and (p.groups[0].first, p.groups[0].last) == (0, 5)
    assert p.groups[0].on_release.target == "Idle_005" and p.dirty      # the rule followed the old frame 4


def test_clone_before_the_copied_frame():
    from src.core.edit import clone_frame
    p = numbered()
    idx = clone_frame(p, Frame("Idle_002", p.frames[1].image), 1, False)    # before frame 2
    assert idx == 1 and labels(p) == ["Idle_001", "Idle_002", "Idle_003", "Idle_004", "Idle_005", "Idle_006"]
    assert p.frames[1].image is p.frames[2].image


def test_the_issue_example_frames_3_to_8():
    from src.core.edit import clone_frame
    p = numbered(8)
    p.groups[0] = Group("Idle", 2, 7)
    clone_frame(p, p.frames[3], 3, False)                    # a copy of frame 4 before frame 4
    assert labels(p)[3] == "Idle_004" and labels(p)[8] == "Idle_009" and labels(p)[2] == "Idle_003"
    assert (p.groups[0].first, p.groups[0].last) == (2, 8)


def test_clone_outside_a_group_stays_outside_every_group():
    from src.core.edit import clone_frame
    p = make_project(groups=[Group("A", 3, 4)])
    idx = clone_frame(p, Frame("f1", p.frames[1].image), 1, True)
    assert idx == 2 and p.frames[2].label == "f1_003" and len(p.frames) == 7
    assert group_of_frame(p) == [None, None, None, None, "A", "A", None] and (p.groups[0].first, p.groups[0].last) == (4, 5)


def test_clone_joins_only_its_own_group():
    from src.core.edit import clone_frame
    p = numbered(3)
    p.frames.append(Frame("Jump_004", Image.new("RGB", (4, 4))))
    clone_frame(p, p.frames[3], 3, False)                    # a Jump copy before Jump: Jump is outside every group
    assert labels(p) == ["Idle_001", "Idle_002", "Idle_003", "Jump_004", "Jump_005"] and p.groups[0].last == 2
    assert group_of_frame(p)[3] is None


def test_clone_stops_at_120_frames():
    from src.core.edit import clone_frame
    p = make_project(120)
    with pytest.raises(EditError, match="at most 120"):
        clone_frame(p, p.frames[0], 0, True)
    assert len(p.frames) == 120
