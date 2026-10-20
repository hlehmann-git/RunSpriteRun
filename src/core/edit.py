"""Edits to a project: rename a label, reorder frames, delete a group (FR-3.2, FR-3.11).
Pure logic with no UI. Anything that needs the owner's confirmation is passed in as a function."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from .colour import Colour
from . import groups as group_rules
from .project import Frame, Group, Project, Rule
from .rules import MAX_FRAMES, MAX_GROUPS, make_label, name_of, old_label_name, valid_frame_name, valid_group_name

MSG_LABEL_CHARS = "Names can only use letters, numbers, - and _ (no spaces)."
MSG_NAME_EMPTY = "A frame needs a name."
MSG_LAST_FRAME = "A project needs at least one frame."


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
    for cr in project.control_rules:
        if cr.release is not None:
            yield cr.release
    if project.start_state is not None:
        yield project.start_state


def group_of_frame(project: Project) -> list[str | None]:
    """The group name of every frame, or None (a frame is in at most one group)."""
    member: list[str | None] = [None] * len(project.frames)
    for g in project.groups:
        for i in range(g.first, g.last + 1):
            member[i] = g.name
    return member


def _drop_control_rules(project: Project, gone_groups: set[str], reset: list[str] | None = None,
                        gone_labels: set[str] = frozenset()) -> None:
    """Frame Group Control rules: a rule that plays a deleted group goes with it; a 'when released' target that is gone
    is cleared (the rule then uses its group's On Release)."""
    from .rules import keys_text
    keep = []
    for cr in project.control_rules:
        if cr.group in gone_groups:
            continue
        r = cr.release
        if r is not None and ((r.kind == "group" and r.target in gone_groups) or (r.kind == "frame" and r.target in gone_labels)):
            cr.release = None
            if reset is not None:
                reset.append(f"rule {keys_text(cr.keys)} (When released)")
        keep.append(cr)
    project.control_rules = keep


def delete_group(project: Project, name: str) -> list[str]:
    """Remove a group. Rules that pointed to it are cleared; returns where that happened,
    for the 'These rules pointed to <name> and have been reset' message."""
    project.groups = [g for g in project.groups if g.name != name]
    reset: list[str] = []
    for g in project.groups:
        if g.on_release is not None and g.on_release.kind == "group" and g.on_release.target == name:
            g.on_release = None
            reset.append(f"group {g.name} (On Release)")
    _drop_control_rules(project, {name}, reset)
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
    _drop_control_rules(project, {g.name for g in removed})
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


def clone_frames(project: Project, srcs: list[Frame], ref: int, after: bool) -> int:
    """Timeline Paste of several frames: put copies of `srcs` (in order) as one block just before or after frame `ref` and
    return the index of the first copy. Each copy keeps its source's name, takes its position number and joins the
    group of frame `ref`, if it has one. Raises EditError if the block would pass the 120 frame limit."""
    if len(project.frames) + len(srcs) > MAX_FRAMES:
        raise EditError(MSG_FRAME_LIMIT)
    join = group_of_frame(project)[ref]
    index = ref + 1 if after else ref
    first = index
    for k, src in enumerate(srcs):
        frame = Frame(make_label(name_of(src.label), 0), src.image, layers=src.layers)
        insert_frame(project, index + k, frame, join=join)
    return first


# ---- delete frames --------------------------------------------------------------------------------------
@dataclass
class DeletePlan:
    emptied: list[str] = field(default_factory=list)     # groups left with no frames, which go too
    resets: list[str] = field(default_factory=list)      # rules that pointed at deleted frames or groups and are reset


def _kt(keys) -> str:
    from .rules import keys_text
    return keys_text(keys)


def plan_delete(project: Project, indices) -> DeletePlan:
    """What deleting these frames would do. Raises EditError if nothing valid is chosen or no frame would be left."""
    gone = set(indices)
    if not gone or not all(0 <= i < len(project.frames) for i in gone):
        raise EditError("There are no frames to delete.")
    if len(gone) >= len(project.frames):
        raise EditError(MSG_LAST_FRAME)
    labels = {project.frames[i].label for i in gone}
    plan = DeletePlan()
    plan.emptied = [g.name for g in project.groups if all(i in gone for i in range(g.first, g.last + 1))]

    def points_away(rule: Rule | None) -> bool:
        return rule is not None and ((rule.kind == "frame" and rule.target in labels)
                                     or (rule.kind == "group" and rule.target in plan.emptied))
    for g in project.groups:
        if g.name not in plan.emptied and points_away(g.on_release):
            plan.resets.append(f"group {g.name} (On Release)")
    for cr in project.control_rules:
        if cr.group in plan.emptied:
            plan.resets.append(f"rule {_kt(cr.keys)} (Frame Group Control)")
        elif points_away(cr.release):
            plan.resets.append(f"rule {_kt(cr.keys)} (When released)")
    if points_away(project.start_state):
        plan.resets.append("Start state")
    return plan


def delete_frames(project: Project, indices) -> DeletePlan:
    """Remove the frames at `indices`. Groups keep their remaining frames, a group with none left is deleted, rules that
    pointed at what is gone are reset, and every frame is numbered by its position again."""
    plan = plan_delete(project, indices)
    gone = set(indices)
    labels = {project.frames[i].label for i in gone}
    for g in project.groups:
        r = g.on_release
        if r is not None and ((r.kind == "frame" and r.target in labels) or (r.kind == "group" and r.target in plan.emptied)):
            g.on_release = None
    _drop_control_rules(project, set(plan.emptied), None, labels)
    s = project.start_state
    if s is not None and ((s.kind == "frame" and s.target in labels) or (s.kind == "group" and s.target in plan.emptied)):
        project.start_state = None
    new_index = {}
    for i in range(len(project.frames)):
        if i not in gone:
            new_index[i] = len(new_index)
    kept_groups = []
    for g in project.groups:
        if g.name in plan.emptied:
            continue
        members = [new_index[i] for i in range(g.first, g.last + 1) if i in new_index]
        g.first, g.last = members[0], members[-1]
        kept_groups.append(g)
    project.groups = kept_groups
    project.frames[:] = [f for i, f in enumerate(project.frames) if i not in gone]
    renumber(project)
    project.dirty = True
    return plan
