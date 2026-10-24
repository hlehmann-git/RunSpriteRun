"""Project save and open (FR-4.4): one .rsr file, which is a ZIP holding project.json
and one PNG per frame. Unknown fields in project.json are ignored so later versions can add data."""
from __future__ import annotations

import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

from src.core.layers import colours_of, flatten
from src.core.project import ControlRule, Frame, Group, Project, Rule, Transition
from src.core.rules import ACTION_KEYS, has_opposites
from src.core.rules import FPS_CHOICES, MAX_FRAMES, MAX_SIZE, MIN_SIZE, valid_group_name, valid_label, valid_project_name
from src.core.systems import get_system

FORMAT_VERSION = 1
MAX_ENTRY_BYTES = 8 * 1024 * 1024


class ProjectFileError(Exception):
    """The file is damaged, unreadable or from another version. Nothing is opened partly."""


class InvalidNameError(ProjectFileError):
    """A group name in the file breaks the naming rules. RunSpriteRun never saves such a name, so the file was
    changed outside the program; it is refused because names become parts of file names on Save and Export."""

    MESSAGE = ("contains a frame group name that RunSpriteRun does not allow (names can only use letters, "
               "numbers, - and _). The file was changed outside RunSpriteRun, so it was not opened.")


def _rule_to_json(r: Rule | None):
    return None if r is None else {"kind": r.kind, "target": r.target, "loop": r.loop, "once": r.once}


def _rule_from_json(d) -> Rule | None:
    if d is None:
        return None
    return Rule(kind=d["kind"], target=d["target"], loop=bool(d.get("loop", False)), once=bool(d.get("once", False)))


LAYER_FILES = ("fg", "core", "bg")


def _frame_json(i: int, f: Frame) -> dict:
    d = {"label": f.label, "file": f"frames/{i + 1:03d}.png", "copied": f.copied}
    if f.layers is not None:          # V2.0: the flat picture above is still written, so v1.0 can read the file
        d["layers"] = [f"layers/{i + 1:03d}_{n}.png" for n in LAYER_FILES]
    return d


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def save_project(project: Project, path: str | Path) -> None:
    """Write atomically: a failed save leaves any existing file untouched."""
    path = Path(path)
    project.palette()                         # bring the saved palette order up to date
    meta = {
        "format_version": FORMAT_VERSION,
        "app": "RunSpriteRun",
        "name": project.name,
        "system": project.system.name,
        "width": project.width,
        "height": project.height,
        "fps": project.fps,
        "transparent": list(project.transparent),
        "written_files": list(project.written_files),
        "extra_colours": [list(c) for c in project.extra_colours],
        "palette_saved": True,                # the list above is the whole palette in slot order (kept colours included)
        "frames": [_frame_json(i, f) for i, f in enumerate(project.frames)],
        "groups": [{"name": g.name, "first": g.first, "last": g.last, "key": g.key,
                    "on_release": _rule_to_json(g.on_release), "colour": list(g.colour)}
                   for g in project.groups],
        "start_state": _rule_to_json(project.start_state),
        "control_rules": [{"keys": list(r.keys), "group": r.group, "once": r.once, "release": _rule_to_json(r.release),
                           "only_in": list(r.only_in)}
                          for r in project.control_rules],          # Frame Group Control rules, top rule first
        "transitions": [{"from": list(t.from_groups), "to": t.to, "play": t.play, "interruptible": t.interruptible}
                        for t in project.transitions],
        "labels": "numbered",          # labels are name_NNN (NNN = position); files without this are converted on opening
    }
    fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=path.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("project.json", json.dumps(meta, indent=2))
            for i, f in enumerate(project.frames):
                z.writestr(f"frames/{i + 1:03d}.png", _png(f.image))
                if f.layers is not None:
                    for n, im in zip(LAYER_FILES, f.layers):
                        z.writestr(f"layers/{i + 1:03d}_{n}.png", _png(im))
        os.replace(tmp, path)
        project.file_path = str(path)
        project.dirty = False
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _read(z: zipfile.ZipFile, name: str) -> bytes:
    try:
        info = z.getinfo(name)
    except KeyError:
        raise ProjectFileError(f"Missing {name}.") from None
    if info.file_size > MAX_ENTRY_BYTES:
        raise ProjectFileError(f"{name} is too large.")
    return z.read(name)


def open_project(path: str | Path) -> Project:
    """Open and fully check a .rsr file. Raises ProjectFileError; never returns a partial project."""
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as z:
            meta = json.loads(_read(z, "project.json"))
            if not isinstance(meta, dict):
                raise ProjectFileError("project.json is not valid.")
            if meta.get("app") != "RunSpriteRun" or meta.get("format_version") != FORMAT_VERSION:
                raise ProjectFileError("This file was saved by a different version of RunSpriteRun.")

            name = meta["name"]
            if not isinstance(name, str) or not valid_project_name(name):
                raise ProjectFileError("The project name in the file is not valid.")
            try:
                system = get_system(meta["system"])
            except KeyError:
                if meta.get("system") == "Sega Master System":
                    raise ProjectFileError("Sega Master System is no longer supported, so this project cannot be opened.") from None
                raise ProjectFileError("The file names an unknown system.") from None
            w, h, fps = meta["width"], meta["height"], meta["fps"]
            if not (isinstance(w, int) and isinstance(h, int) and MIN_SIZE <= w <= MAX_SIZE and MIN_SIZE <= h <= MAX_SIZE):
                raise ProjectFileError("The frame size in the file is not valid.")
            if fps not in FPS_CHOICES:
                raise ProjectFileError("The frames per second in the file is not valid.")

            entries = meta["frames"]
            if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_FRAMES:
                raise ProjectFileError("The number of frames in the file is not valid.")


            def load_image(name: str) -> Image.Image:
                with Image.open(io.BytesIO(_read(z, name))) as im:
                    img = im.convert("RGB") if im.mode != "RGB" else im.copy()
                if img.size != (w, h):
                    raise ProjectFileError("A frame does not match the project frame size.")
                if system.snap_image(img) is not img:
                    raise ProjectFileError("A frame contains colours that are not valid for the system.")
                return img
            transparent = tuple(meta["transparent"])
            if len(transparent) != 3 or any(not isinstance(v, int) for v in transparent):
                raise ProjectFileError("The transparent colour in the file is not valid.")
            frames: list[Frame] = []
            used: set = set()
            labels: set[str] = set()
            for e in entries:
                label = e["label"]
                if not isinstance(label, str) or not valid_label(label) or label.lower() in labels:
                    raise ProjectFileError("A frame label in the file is not valid.")
                labels.add(label.lower())
                img = load_image(e["file"])
                layers = None
                if e.get("layers") is not None:
                    names = e["layers"]
                    if not (isinstance(names, list) and len(names) == 3):
                        raise ProjectFileError("A frame's layers in the file are not valid.")
                    layers = tuple(load_image(n) for n in names)
                    img = flatten(layers, transparent)              # the layers decide; the flat picture follows them
                    for im in layers:
                        used |= colours_of(im)
                used |= colours_of(img)
                frames.append(Frame(label, img, layers=layers))

            extra = []
            for c in meta.get("extra_colours", []):
                c = tuple(c)
                if len(c) != 3 or any(not isinstance(v, int) for v in c) or not system.valid(c):
                    raise ProjectFileError("A colour in the file is not valid for the system.")
                extra.append(c)
            if len(used | {transparent} | set(extra)) > system.max_colours:
                raise ProjectFileError("The frames use more colours than the system allows.")

            # (older files may hold a sprite sheet gap: it is ignored, sheets no longer have one)
            from src.io.export import clean_written_list
            written = clean_written_list(meta.get("written_files", []))

            groups = [Group(name=g["name"], first=g["first"], last=g["last"], key=g.get("key"),
                            on_release=_rule_from_json(g.get("on_release")),
                            colour=tuple(g.get("colour", (0, 0, 0))))
                      for g in meta.get("groups", [])]
            group_names: set[str] = set()
            for g in groups:
                if not isinstance(g.name, str) or not valid_group_name(g.name) or g.name.lower() in group_names:
                    raise InvalidNameError("A frame group name in the file is not valid.")
                group_names.add(g.name.lower())
                if not (isinstance(g.first, int) and isinstance(g.last, int) and 0 <= g.first <= g.last < len(frames)):
                    raise ProjectFileError("A frame group in the file is outside the frames.")

            control = []
            names = {g.name for g in groups}
            for d in meta.get("control_rules", []):                    # a damaged or out-of-date rule is dropped, never the project
                try:
                    keys = [k for k in d["keys"]]
                    if (keys and all(isinstance(k, str) and k in ("W", "A", "S", "D", "1", "2", "3", "4", "5", "6") + ACTION_KEYS for k in keys)
                            and not (len(keys) > 1 and any(k in ACTION_KEYS for k in keys))      # an action key stands alone
                            and len(set(keys)) == len(keys) and not has_opposites(keys) and d["group"] in names):
                        only_in = [str(x) for x in d.get("only_in", [])]
                        if d.get("from_group"):                       # a v2.0.10 or v2.0.11 file: one group
                            only_in.append(str(d["from_group"]))
                        if all(x in names for x in only_in):
                            control.append(ControlRule(keys, d["group"], bool(d.get("once", False)), _rule_from_json(d.get("release")),
                                                       only_in))
                except (KeyError, TypeError, ValueError):
                    continue
            transitions = []
            for d in meta.get("transitions", []):
                try:
                    frm = [str(x) for x in d.get("from", [])]
                    if d["to"] in names and d["play"] in names and d["to"] != d["play"] and all(x in names for x in frm):
                        transitions.append(Transition(frm, str(d["to"]), str(d["play"]), bool(d.get("interruptible", False))))
                except (KeyError, TypeError, ValueError, AttributeError):
                    continue
            project = Project(name=name, system=system, width=w, height=h, fps=fps,
                              transparent=transparent, written_files=written, frames=frames, groups=groups,
                              extra_colours=extra, start_state=_rule_from_json(meta.get("start_state")), control_rules=control, transitions=transitions, file_path=str(path), dirty=False)
            if not meta.get("palette_saved"):         # an older project: the palette keeps its old order, then is saved from now on
                used_now = list(project._used_colours())
                project.extra_colours = used_now + [c for c in extra if c not in used_now]
            from src.core import edit
            if meta.get("labels") == "numbered":
                edit.renumber(project)
            else:
                edit.convert_old_labels(project)               # an older project: converted without a message
            project.dirty = False
            return project
    except ProjectFileError:
        raise
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, KeyError, TypeError, ValueError, SyntaxError):
        raise ProjectFileError("The file is damaged or is not a RunSpriteRun project.") from None
