"""Edits to a project: rename a label, reorder frames, delete a group (FR-3.2, FR-3.11).
Pure logic with no UI. Anything that needs the owner's confirmation is passed in as a function."""
from __future__ import annotations

import re
from typing import Callable

from .colour import Colour
from . import groups as group_rules
from .project import Frame, Group, Project, Rule
from .rules import LABEL_MAX, MAX_FRAMES, MAX_GROUPS, copy_label, valid_group_name, valid_label

MSG_LABEL_CHARS = "Labels can only use letters, numbers, - and _ (no spaces)."
MSG_LABEL_DUPLICATE = "Frame labels must be unique."


class EditError(ValueError):
    """The edit is refused; the message is the one to show the owner."""


def rename_label(project: Project, index: int, new: str) -> bool:
    """Set a frame's label. Returns False if nothing changed. Rules that pointed to the old label follow."""
    old = project.frames[index].label
    if new == old:
        return False
    if not valid_label(new):
        raise EditError(MSG_LABEL_CHARS)
    if any(f.label.lower() == new.lower() for i, f in enumerate(project.frames) if i != index):
        raise EditError(MSG_LABEL_DUPLICATE)
    project.frames[index].label = new
    project.frames[index].copied = False                     # a label chosen by the owner is no longer red
    for rule in _all_rules(project):
        if rule.kind == "frame" and rule.target == old:
            rule.target = new
    project.dirty = True
    return True


def _all_rules(project: Project):
    for g in project.groups:
        if g.on_release is not None:
            yield g.on_release
    if project.start_state is not None:
        yield project.start_state


def group_of_frame(project: Project) -> list[str | None]:
    """The group name of every frame, or None (a frame is in at most one group)."""
    member: list[str | None] = [None] * len(project.frames)
    for g in project.groups:
        for i in range(g.first, g.last + 1):
            member[i] = g.name
    return member


def delete_group(project: Project, name: str) -> list[str]:
    """Remove a group. Rules that pointed to it are cleared; returns where that happened,
    for the 'These rules pointed to <name> and have been reset' message."""
    project.groups = [g for g in project.groups if g.name != name]
    reset: list[str] = []
    for g in project.groups:
        if g.on_release is not None and g.on_release.kind == "group" and g.on_release.target == name:
            g.on_release = None
            reset.append(f"group {g.name} (On Release)")
    if project.start_state is not None and project.start_state.kind == "group" and project.start_state.target == name:
        project.start_state = None
        reset.append("Start state")
    project.dirty = True
    return reset


def move_frame(project: Project, src: int, dst: int,
               confirm_delete: Callable[[list[str]], bool] = lambda names: True) -> bool:
    """Move the frame at `src` so that it ends up at index `dst` (FR-3.2).

    Group rules: the moved frame joins a group only if the frames on both sides of its new place
    belong to that same group, except that moving inside its own group (up to and including the
    first and last places of that group) keeps it there; otherwise it belongs to no group. A group left with no frames is
    deleted after `confirm_delete` agrees; if it does not, nothing changes.
    Returns True if the project changed."""
    n = len(project.frames)
    if not (0 <= src < n and 0 <= dst < n):
        raise IndexError("frame index out of range")
    if src == dst:
        return False

    member = group_of_frame(project)
    moved_member = member.pop(src)
    left = member[dst - 1] if dst > 0 else None
    right = member[dst] if dst < n - 1 else None
    new_member = left if (left is not None and left == right) else None
    if moved_member is not None:
        # Reordering inside its own group, including its first and last places, keeps the frame in it.
        own = [i for i, m in enumerate(member) if m == moved_member]
        if own and own[0] <= dst <= own[-1] + 1:
            new_member = moved_member
    member.insert(dst, new_member)

    emptied = [g.name for g in project.groups if g.name not in member]
    if emptied and not confirm_delete(emptied):
        return False

    frame = project.frames.pop(src)
    project.frames.insert(dst, frame)
    kept: list[Group] = []
    for g in project.groups:
        idx = [i for i, m in enumerate(member) if m == g.name]
        if not idx:
            continue
        g.first, g.last = idx[0], idx[-1]
        kept.append(g)
    removed = [g for g in project.groups if g not in kept]
    project.groups = kept
    for g in removed:                              # clear rules pointing at deleted groups
        for other in project.groups:
            if other.on_release is not None and other.on_release.kind == "group" and other.on_release.target == g.name:
                other.on_release = None
        if project.start_state is not None and project.start_state.kind == "group" and project.start_state.target == g.name:
            project.start_state = None
    project.dirty = True
    return True


def check_copy(project: Project, name: str, first: int, last: int) -> None:
    """Raise GroupError if frames first..last (0-based) cannot be copied into a new group called `name`."""
    if not valid_group_name(name):
        raise group_rules.GroupError(group_rules.MSG_NAME_CHARS)
    if any(g.name.lower() == name.lower() for g in project.groups):
        raise group_rules.GroupError(group_rules.MSG_NAME_DUPLICATE)
    if len(project.groups) >= MAX_GROUPS:
        raise group_rules.GroupError(group_rules.MSG_GROUP_LIMIT)
    if first > last:
        raise group_rules.GroupError(group_rules.MSG_FROM_AFTER_TO)
    if not (0 <= first and last < len(project.frames)):
        raise group_rules.GroupError("The frames are outside the timeline.")
    if len(project.frames) + (last - first + 1) > MAX_FRAMES:
        raise group_rules.GroupError(group_rules.MSG_FRAME_LIMIT)


def copy_into_new_group(project: Project, name: str, first: int, last: int, key: str | None,
                        on_release: Rule | None, colour: Colour) -> Group:
    """Copy frames first..last to the end of the timeline as a new group. The copies are labelled with the
    original label plus _001 (_002 ...) and are flagged so the timeline shows them red until renamed."""
    check_copy(project, name, first, last)
    labels = {f.label for f in project.frames}
    start = len(project.frames)
    for i in range(first, last + 1):
        src = project.frames[i]
        label = copy_label(src.label, labels)
        labels.add(label)
        project.frames.append(Frame(label, src.image, copied=True, layers=src.layers))     # images are never changed in place
    try:
        return group_rules.save_group(project, None, name, start, len(project.frames) - 1, key, on_release, colour)
    except Exception:
        del project.frames[start:]
        raise


# ---- V2.0: a new frame made in Edit mode ---------------------------------------------------------------
MSG_FRAME_LIMIT = f"A project can have at most {MAX_FRAMES} frames."


def new_frame_label(project: Project) -> str:
    """Frame_<n>, the first number not already used as a label."""
    used = {f.label.lower() for f in project.frames}
    n = len(project.frames) + 1
    while f"frame_{n}" in used:
        n += 1
    return f"Frame_{n}"


_NUMBERED = re.compile(r"^(.*_)(\d+)$")


def _group_numbering(project: Project, group: Group, skip: int) -> str | None:
    """The shared text before the final number of the labels in `group` (for example "Idle_"), or None when the
    labels do not all look like <text>_<number> with the same text. `skip` is a frame index to leave out."""
    prefixes = set()
    for i in range(group.first, group.last + 1):
        if i == skip:
            continue
        m = _NUMBERED.match(project.frames[i].label)
        if not m:
            return None
        prefixes.add(m.group(1))
    return prefixes.pop() if len(prefixes) == 1 else None


def insert_frame(project: Project, index: int, frame: Frame, join: str | None = None, anchor: int | None = None,
                 after: bool = True) -> Group | None:
    """Put `frame` at `index`. If `join` names a group the frame becomes a member and the group grows (it can be the
    first or last frame of it). A frame that joins a group whose labels all look like Idle_1, Idle_2 ... is labelled
    to fit its place (Idle_4 when it goes after Idle_3) and the later frames of the group are renumbered only as far
    as needed to keep labels unique; rules that pointed at renamed labels follow them. `anchor` is the index (before
    the insert) of the frame it was inserted next to, and `after` says on which side. Returns the group joined."""
    if len(project.frames) >= MAX_FRAMES:
        raise EditError(MSG_FRAME_LIMIT)
    index = max(0, min(index, len(project.frames)))
    joined = None
    for g in project.groups:
        if join is not None and g.name == join:
            g.first = min(g.first, index)
            g.last = g.last + 1 if index <= g.last + 1 else index
            joined = g
        elif g.first >= index:
            g.first += 1
            g.last += 1
        elif g.last >= index:                    # inserted inside another group's frames: it joins that one
            if join is None:
                g.last += 1
                joined = g
    project.frames.insert(index, frame)
    project.dirty = True
    if joined is not None and anchor is not None:
        _label_in_group(project, joined, index, anchor, after)
    return joined


def _label_in_group(project: Project, group: Group, index: int, anchor: int, after: bool) -> None:
    prefix = _group_numbering(project, group, skip=index)
    if prefix is None:
        return
    anchor_now = anchor + 1 if anchor >= index else anchor          # the anchor frame after the insert
    m = _NUMBERED.match(project.frames[anchor_now].label)
    if not m:
        return
    digits = m.group(2)
    width = len(digits) if digits.startswith("0") else 0
    n = int(digits) + (1 if after else 0)
    fmt = lambda k: f"{prefix}{k:0{width}d}"
    plan = {index: fmt(n)}                                           # frame index -> new label
    last = n
    for i in range(index + 1, group.last + 1):
        k = int(_NUMBERED.match(project.frames[i].label).group(2))
        if k <= last:
            k = last + 1
            plan[i] = fmt(k)
        last = k
    renamed = {project.frames[i].label for i in plan if i != index}
    others = {f.label.lower() for i, f in enumerate(project.frames) if i not in plan and f.label not in renamed}
    new_labels = list(plan.values())
    if (any(len(x) > LABEL_MAX for x in new_labels) or len({x.lower() for x in new_labels}) != len(new_labels)
            or any(x.lower() in others for x in new_labels)):
        return                                                       # would clash: keep the plain Frame_<n> label
    mapping = {project.frames[i].label: lab for i, lab in plan.items() if i != index}
    for i, lab in plan.items():
        project.frames[i].label = lab
        project.frames[i].copied = project.frames[i].copied if i != index else False
    for rule in _all_rules(project):                                 # rules follow the renamed frames (all at once)
        if rule.kind == "frame" and rule.target in mapping:
            rule.target = mapping[rule.target]
