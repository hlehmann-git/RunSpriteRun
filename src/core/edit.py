"""Edits to a project: rename a label, reorder frames, delete a group (FR-3.2, FR-3.11).
Pure logic with no UI. Anything that needs the owner's confirmation is passed in as a function."""
from __future__ import annotations

from collections import Counter
from typing import Callable

from .colour import Colour
from . import groups as group_rules
from .project import Frame, Group, Project, Rule
from .rules import MAX_FRAMES, MAX_GROUPS, make_label, name_of, old_label_name, valid_frame_name, valid_group_name

MSG_LABEL_CHARS = "Names can only use letters, numbers, - and _ (no spaces)."
MSG_NAME_EMPTY = "A frame needs a name."


class EditError(ValueError):
    """The edit is refused; the message is the one to show the owner."""


def _apply_names(project: Project, names: list[str]) -> bool:
    """Give frame i the label <names[i]>_<i+1, three digits>. Rules that pointed at a renamed label follow it.
    Returns True if any label changed."""
    old = [f.label for f in project.frames]
    seen = Counter(old)
    mapping: dict[str, str] = {}
    for i, f in enumerate(project.frames):
        new = make_label(names[i], i + 1)
        if new != f.label:
            if seen[f.label] == 1:
                mapping[f.label] = new
            f.label = new
    if not mapping and old == [f.label for f in project.frames]:
        return False
    for rule in _all_rules(project):
        if rule.kind == "frame" and rule.target in mapping:
            rule.target = mapping[rule.target]
    project.dirty = True
    return True


def renumber(project: Project) -> bool:
    """Every frame's number becomes its position (001 to 120); names are kept."""
    return _apply_names(project, [name_of(f.label) for f in project.frames])


def convert_old_labels(project: Project) -> None:
    """A project saved before label numbering: the name is the old label without a trailing _number, the number is the
    frame's position. Done without a message; the project is not marked as changed."""
    dirty = project.dirty
    for f in project.frames:
        f.copied = False
    _apply_names(project, [old_label_name(f.label) for f in project.frames])
    project.dirty = dirty


def rename_label(project: Project, index: int, new: str) -> bool:
    """Set the name of a frame (the number is not touched). A frame in a group renames the whole group.
    Returns False if nothing changed. Rules that pointed to a renamed label follow it."""
    if not new:
        raise EditError(MSG_NAME_EMPTY)
    if not valid_frame_name(new):
        raise EditError(MSG_LABEL_CHARS)
    group = next((g for g in project.groups if g.first <= index <= g.last), None)
    targets = range(group.first, group.last + 1) if group else [index]
    names = [name_of(f.label) for f in project.frames]
    for i in targets:
        names[i] = new
    for i in targets:
        project.frames[i].copied = False
    return _apply_names(project, names)


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
    renumber(project)
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
    """Copy frames first..last to the end of the timeline as a new group. The copies are named after the new group
    and numbered by their positions (IdleSlow_005, IdleSlow_006)."""
    check_copy(project, name, first, last)
    start = len(project.frames)
    for i in range(first, last + 1):
        src = project.frames[i]
        project.frames.append(Frame(make_label(name, 0), src.image, layers=src.layers))     # images are never changed in place
    try:
        group = group_rules.save_group(project, None, name, start, len(project.frames) - 1, key, on_release, colour)
    except Exception:
        del project.frames[start:]
        raise
    renumber(project)
    return group


# ---- V2.0: a new frame made in Edit mode ---------------------------------------------------------------
MSG_FRAME_LIMIT = f"A project can have at most {MAX_FRAMES} frames."


def new_frame_label(project: Project) -> str:
    """The label of a new blank frame before it is numbered: Frame (insert_frame numbers it)."""
    return make_label("Frame", 0)


def insert_frame(project: Project, index: int, frame: Frame, join: str | None = None, anchor: int | None = None,
                 after: bool = True) -> Group | None:
    """Put `frame` at `index`. If `join` names a group the frame becomes a member and the group grows (it can be the
    first or last frame of it). Every frame is then numbered by its position again. (`anchor` and `after` are no
    longer needed and are kept only so that callers need not change.) Returns the group joined."""
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
    renumber(project)
    project.dirty = True
    return joined


def clone_frame(project: Project, src: Frame, ref: int, after: bool) -> int:
    """Timeline Paste: put a copy of `src` just before or after frame `ref` (the frame that was copied) and return the
    copy's index. The copy keeps that frame's name, takes its position number and joins the group of frame `ref`, if
    it has one. Raises EditError at the 120 frame limit."""
    if len(project.frames) >= MAX_FRAMES:
        raise EditError(MSG_FRAME_LIMIT)
    frame = Frame(make_label(name_of(project.frames[ref].label), 0), src.image, layers=src.layers)
    index = ref + 1 if after else ref
    insert_frame(project, index, frame, join=group_of_frame(project)[ref])
    return index
