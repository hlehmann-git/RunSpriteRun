import json

from PIL import Image

from src.core.project import ControlRule, Frame, Group, Project, Rule
from src.core.systems import get_system
from src.io import export, rules_export
from src.io.save import save_whole


def proj(system="Sega Genesis / Mega Drive"):
    frames = [Frame(f"Walk_{i + 1:03d}", Image.new("RGB", (4, 4))) for i in range(8)]
    gs = [Group("Idle", 0, 1, on_release=None), Group("WalkRight", 2, 4, key="D", on_release=Rule("group", "Idle", True)),
          Group("Up", 5, 5, key="W+D"), Group("Shoot", 6, 7)]
    return Project("Demo", get_system(system), 4, 4, frames=frames, groups=gs, dirty=False,
                   control_rules=[ControlRule(["1", "W", "D"], "Shoot", once=True, release=Rule("frame", "Walk_001"))])


def test_rule_rows_order_and_content():
    rows = rules_export.rule_rows(proj())
    assert [(r["source"], r["keys"], r["plays"], r["mode"]) for r in rows] == [
        ("frame_group_control", ["W", "D", "1"], "Shoot", "play_once"),
        ("group_key", ["W", "D"], "Up", "loop"),                 # a diagonal beats a single key
        ("group_key", ["D"], "WalkRight", "loop")]


def test_text_is_tab_separated_tables():
    t = rules_export.rules_text(proj())
    lines = t.splitlines()
    assert lines[2].split("\t") == ["Priority", "Source", "Keys", "Only if in", "Plays", "Mode", "When released"]
    assert lines[3].split("\t") == ["1", "Frame Group Control", "W+D+1", "", "Shoot", "Play once", "Go To Frame Walk_001"]
    assert "WalkRight\t3\t5\t3\tWalk_003\tWalk_005\tD\tDemo_WalkRight_SpriteSheet.png" in t


def test_json_is_valid_and_complete():
    d = json.loads(rules_export.rules_json(proj()))
    assert d["controller"]["buttons"] == ["1", "2", "3"] and d["project"]["frames_per_second"] == 12
    assert d["rules"][0]["priority"] == 1 and d["rules"][0]["when_released"] == {"go_to": "frame", "target": "Walk_001"}
    g = next(x for x in d["groups"] if x["name"] == "WalkRight")
    assert g["first_frame"] == 3 and g["frames"][0]["label"] == "Walk_003" and d["how_to_read"]


def test_written_by_export_and_by_save(tmp_path):
    p = proj()
    export.write_all(p, tmp_path / "out", p.transparent, with_data=False)
    assert (tmp_path / "out" / "Demo_Rules.txt").is_file() and (tmp_path / "out" / "Demo_Rules.json").is_file()
    save_whole(p, tmp_path / "proj" / "Demo.rsr")
    assert (tmp_path / "proj" / "Demo_Rules.json").is_file()
    assert "Demo_Rules.txt" not in " ".join(p.written_files)         # never part of the stale-file clean-up list
