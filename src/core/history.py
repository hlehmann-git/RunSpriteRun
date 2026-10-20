"""Undo / redo (FR-2.2): up to 50 steps. A snapshot holds everything an edit can change; frame images are
never changed in place (a palette replacement makes new images), so a snapshot keeps references."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from PIL import Image

from .colour import Colour
from .project import Frame, Group, Project, Rule

LIMIT = 50


@dataclass
class Snapshot:
    frames: list[tuple[str, Image.Image, bool, tuple | None]]       # label, image, copied, layers
    groups: list[Group]
    start_state: Rule | None
    fps: int
    transparent: Colour
    extra_colours: tuple = ()
    control_rules: list = field(default_factory=list)

    def same_as(self, other: "Snapshot") -> bool:
        return (len(self.frames) == len(other.frames)
                and all(a[0] == b[0] and a[1] is b[1] and a[2] == b[2] and a[3] is b[3] for a, b in zip(self.frames, other.frames))
                and self.groups == other.groups and self.start_state == other.start_state
                and self.fps == other.fps and self.transparent == other.transparent and self.extra_colours == other.extra_colours
                and self.control_rules == other.control_rules)


def take(project: Project) -> Snapshot:
    project.palette()                      # bring the saved palette up to date, so a snapshot holds the whole palette
    return Snapshot([(f.label, f.image, f.copied, f.layers, f.uid) for f in project.frames], copy.deepcopy(project.groups),
                    copy.deepcopy(project.start_state), project.fps, project.transparent,
                    tuple(project.extra_colours), copy.deepcopy(project.control_rules))


def restore(project: Project, snap: Snapshot) -> None:
    project.frames[:] = [Frame(label, image, copied, layers, uid) for label, image, copied, layers, uid in snap.frames]   # the count can change
    project.groups[:] = copy.deepcopy(snap.groups)
    project.start_state = copy.deepcopy(snap.start_state)
    project.fps = snap.fps
    project.transparent = snap.transparent
    project.extra_colours = list(snap.extra_colours)
    project.control_rules = copy.deepcopy(snap.control_rules)
    project.dirty = True


class History:
    def __init__(self) -> None:
        self._undo: list[Snapshot] = []
        self._redo: list[Snapshot] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def push(self, before: Snapshot) -> None:
        """An edit was made; `before` is the state it started from."""
        self._undo.append(before)
        del self._undo[:-LIMIT]
        self._redo.clear()

    def undo(self, current: Snapshot) -> Snapshot | None:
        if not self._undo:
            return None
        self._redo.append(current)
        return self._undo.pop()

    def redo(self, current: Snapshot) -> Snapshot | None:
        if not self._redo:
            return None
        self._undo.append(current)
        return self._redo.pop()
