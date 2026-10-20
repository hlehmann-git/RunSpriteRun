"""The rules files (v2.0.9): <Project>_Rules.txt (tab-separated tables, opens in a spreadsheet) and <Project>_Rules.json
(the same information for a game developer's code). Both are written with every Save and every Export, and on their own
with File > Export Rules. They only describe the project; nothing reads them back."""
from __future__ import annotations

import json
from pathlib import Path

from src.core import sheets
from src.core.project import Project, Rule
from src.core.rules import DIAGONALS, keys_for

SUFFIX_TXT = "_Rules.txt"
SUFFIX_JSON = "_Rules.json"
HOW_TO_READ = [
    "Rules are checked from priority 1 downwards while the player holds keys; the first rule whose keys are all held plays its group.",
    "only_after: when a group name is given, the rule only fires while the frame on screen belongs to that group (for example a turn that plays only after the walk in the other direction). null means always.",
    "Rules from frame_group_control come first. After them come the keys given to a group in Set Frame Group (source group_key): "
    "a diagonal such as W+D beats a single key, otherwise the key pressed last wins.",
    "mode loop: the group repeats while the keys are held. mode play_once: it plays through one time, will not fire again until "
    "the keys are let go, and then the next matching rule takes over.",
    "when_released says what happens when no playable key is held (or a play_once rule ends with nothing held): go to a frame "
    "(shown still), or go to a group (looping or still on its first frame). null means stay on the group's last frame.",
    "Frame numbers are 1-based, as in RunSpriteRun. W A S D are up, left, down, right; 1 to 6 are fire buttons.",
]


def _release_json(r: Rule | None):
    if r is None:
        return None
    return {"go_to": r.kind, "target": r.target, **({"loop": r.loop} if r.kind == "group" else {})}


def _release_text(r: Rule | None) -> str:
    if r is None:
        return "stay on last frame"
    if r.kind == "frame":
        return f"Go To Frame {r.target}"
    return f"Go to Group {r.target}" + (" (loop)" if r.loop else "")


def rule_rows(project: Project) -> list[dict]:
    """Every rule in priority order: the Frame Group Control rules, then the basic key of each group."""
    rows: list[dict] = []
    by_name = {g.name: g for g in project.groups}
    for cr in project.control_rules:
        g = by_name.get(cr.group)
        if g is None:
            continue
        release = cr.release if cr.release is not None else g.on_release
        rows.append({"source": "frame_group_control", "keys": sorted(cr.keys, key="WASD123456".index),
                     "only_after": cr.from_group or None, "plays": cr.group, "mode": "play_once" if cr.once else "loop", "when_released": release})
    keyed = [g for g in project.groups if g.key]
    keyed.sort(key=lambda g: 0 if g.key in DIAGONALS else 1)                       # a diagonal beats a single key
    for g in keyed:
        rows.append({"source": "group_key", "keys": g.key.split("+"), "only_after": None, "plays": g.name, "mode": "loop", "when_released": g.on_release})
    return rows


def group_rows(project: Project) -> list[dict]:
    out = []
    for g in project.groups:
        out.append({
            "name": g.name, "first_frame": g.first + 1, "last_frame": g.last + 1, "frame_count": g.last - g.first + 1,
            "first_label": project.frames[g.first].label, "last_label": project.frames[g.last].label,
            "colour": list(g.colour), "key": g.key,
            "sprite_sheet": sheets.group_sheet_name(project, g.name),
            "frames": [{"number": i + 1, "label": project.frames[i].label, "file": sheets.frame_file_name(project, i)}
                       for i in range(g.first, g.last + 1)],
        })
    return out


def rules_json(project: Project) -> str:
    keys = keys_for(project.system.name)
    doc = {
        "about": "RunSpriteRun frame group rules: which keys play which frame group. Written by RunSpriteRun; not read back.",
        "how_to_read": HOW_TO_READ,
        "project": {"name": project.name, "system": project.system.name, "frame_width": project.width,
                    "frame_height": project.height, "frames_per_second": project.fps, "frame_count": len(project.frames),
                    "all_frames_sprite_sheet": sheets.all_sheet_name(project)},
        "controller": {"directions": ["W", "A", "S", "D"], "diagonals": list(DIAGONALS), "buttons": [k for k in keys if k.isdigit()]},
        "start_state": _release_json(project.start_state),
        "groups": group_rows(project),
        "rules": [{"priority": i + 1, "source": r["source"], "keys": r["keys"], "only_after": r["only_after"], "plays": r["plays"], "mode": r["mode"],
                   "when_released": _release_json(r["when_released"])} for i, r in enumerate(rule_rows(project))],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def rules_text(project: Project) -> str:
    """Tab-separated: a rules table, a blank line, then a groups table."""
    lines = [f"RunSpriteRun rules\t{project.name}\t{project.system.name}\t{project.fps} fps\t{project.width} x {project.height}", "",
             "Priority\tSource\tKeys\tOnly after\tPlays\tMode\tWhen released"]
    for i, r in enumerate(rule_rows(project)):
        src = "Frame Group Control" if r["source"] == "frame_group_control" else "Group key"
        mode = "Play once" if r["mode"] == "play_once" else "Loop"
        lines.append(f"{i + 1}\t{src}\t{'+'.join(r['keys'])}\t{r['only_after'] or ''}\t{r['plays']}\t{mode}\t{_release_text(r['when_released'])}")
    lines += ["", "Group\tFirst frame\tLast frame\tFrames\tFirst label\tLast label\tKey\tSprite sheet"]
    for g in group_rows(project):
        lines.append(f"{g['name']}\t{g['first_frame']}\t{g['last_frame']}\t{g['frame_count']}\t{g['first_label']}\t"
                     f"{g['last_label']}\t{g['key'] or ''}\t{g['sprite_sheet']}")
    return "\n".join(lines) + "\n"


def rules_file_names(project: Project) -> tuple[str, str]:
    return f"{project.name}{SUFFIX_TXT}", f"{project.name}{SUFFIX_JSON}"


def write_rules_files(project: Project, folder: str | Path) -> list[str]:
    """Write both files into `folder` (replacing older copies). Raises OSError."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    txt, js = rules_file_names(project)
    (folder / txt).write_text(rules_text(project), encoding="utf-8", newline="\n")
    (folder / js).write_text(rules_json(project), encoding="utf-8", newline="\n")
    return [txt, js]
