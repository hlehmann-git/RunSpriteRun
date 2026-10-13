from PIL import Image

from src.core.project import Frame, Group, Project, Rule
from src.core.runner import Runner
from src.core.systems import get_system


def make(groups, start=None, n=12):
    frames = [Frame(f"f{i + 1}", Image.new("RGB", (4, 4))) for i in range(n)]
    return Project("P", get_system("Atari ST"), 4, 4, frames=frames, groups=groups, start_state=start, dirty=False)


def shown(r, ticks=0):
    out = [r.frame]
    for _ in range(ticks):
        r.tick()
        out.append(r.frame)
    return out


def test_start_state_default_is_frame_one_and_nothing_happens_before_f5():
    p = make([Group("Walk", 0, 2, key="D")])
    r = Runner(p)
    assert r.frame == 0 and not r.running
    assert r.press("D") is False and r.frame == 0           # keys only work while running
    r.start()
    assert r.frame == 0 and r.running


def test_start_state_frame_and_group():
    p = make([Group("Idle", 3, 5)], start=Rule("frame", "f8"))
    r = Runner(p)
    r.start()
    assert r.frame == 7
    p.start_state = Rule("group", "Idle", True)
    r.start()
    assert shown(r, 4) == [3, 4, 5, 3, 4]                    # loops


def test_start_state_group_without_loop_is_a_still_first_frame():
    p = make([Group("Idle", 3, 5)], start=Rule("group", "Idle", False))
    r = Runner(p)
    r.start()
    assert shown(r, 4) == [3, 3, 3, 3, 3]                    # nothing animates unless Loop is on


def test_key_loops_group_while_held_and_release_applies_resting_state():
    p = make([Group("Walk", 0, 2, key="D", on_release=Rule("frame", "f10")), Group("Idle", 8, 9)])
    r = Runner(p)
    r.start()
    assert r.press("D") and r.playing_group == "Walk"
    assert shown(r, 4) == [0, 1, 2, 0, 1]
    assert r.press("D") is False                             # keyboard auto-repeat is ignored
    r.release("D")
    assert r.frame == 9 and r.playing_group is None          # resting state applies at once
    assert shown(r, 3) == [9, 9, 9, 9]


def test_resting_state_group_loop_on_and_off():
    p = make([Group("Walk", 0, 1, key="D", on_release=Rule("group", "Idle", True)),
              Group("Jump", 4, 5, key="W", on_release=Rule("group", "Idle", False)),
              Group("Idle", 8, 10)])
    r = Runner(p)
    r.start()
    r.press("D")
    r.release("D")
    assert shown(r, 4) == [8, 9, 10, 8, 9]
    r.press("W")
    r.release("W")
    assert shown(r, 5) == [8, 8, 8, 8, 8, 8]                 # Loop off: still first frame of Idle


def test_pressing_a_key_stops_a_resting_loop_and_starts_from_the_first_frame():
    p = make([Group("Walk", 0, 2, key="D", on_release=Rule("group", "Idle", True)), Group("Idle", 8, 10)])
    r = Runner(p)
    r.start()
    r.press("D")
    r.release("D")
    r.tick()
    r.press("D")
    assert r.frame == 0


def test_several_keys_most_recent_wins_and_hands_back():
    p = make([Group("Walk", 0, 2, key="D", on_release=Rule("frame", "f12")),
              Group("Jump", 4, 6, key="W", on_release=Rule("frame", "f11"))])
    r = Runner(p)
    r.start()
    r.press("D")
    r.tick()
    r.press("W")
    assert r.playing_group == "Jump" and r.frame == 4
    r.release("D")                                           # not the one playing: nothing changes
    assert r.playing_group == "Jump"
    r.release("W")                                           # no assigned key held: W's resting state
    assert r.frame == 10
    r.press("D")
    r.press("W")
    r.release("W")                                           # D is still held: it takes over
    assert r.playing_group == "Walk" and r.frame == 0
    r.release("D")
    assert r.frame == 11


def test_keys_without_a_group_do_nothing():
    p = make([Group("Walk", 0, 2, key="D")])
    r = Runner(p)
    r.start()
    assert r.press("A") is False and r.frame == 0 and r.held == []
    assert r.release("A") is False


def test_deleted_target_rules_fall_back():
    p = make([Group("Walk", 2, 4, key="D", on_release=None)], start=Rule("group", "Gone", True))
    r = Runner(p)
    r.start()
    assert r.frame == 0                                      # start state fell back to Go To Frame 1
    r.press("D")
    r.release("D")
    assert r.frame == 4                                      # ignored rule: stop on the group's last frame


def test_stop_returns_to_start_state_and_clears_keys():
    p = make([Group("Walk", 0, 2, key="D")], start=Rule("frame", "f6"))
    r = Runner(p)
    r.start()
    r.press("D")
    r.stop()
    assert not r.running and r.frame == 5 and r.held == []
    assert r.tick() is False


def test_release_all():
    p = make([Group("Walk", 0, 2, key="D"), Group("Jump", 4, 6, key="W")])
    r = Runner(p)
    r.start()
    r.press("D")
    r.press("W")
    r.release_all()
    assert r.held == []


def test_single_frame_group_loops_without_error():
    p = make([Group("One", 3, 3, key="W")])
    r = Runner(p)
    r.start()
    r.press("W")
    assert shown(r, 3) == [3, 3, 3, 3]
