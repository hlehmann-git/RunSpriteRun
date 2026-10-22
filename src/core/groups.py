"""Frame group rules (FR-3.11) and what happens to rules when groups change (FR-3.10 item 8).
Pure logic with no UI. Frame numbers inside this module are 0-based; messages use 1-based numbers."""
from __future__ import annotations

from .colour import Colour
from .project import ControlRule, Group, Project, Rule, Transition
from .rules import ACTION_KEYS, KEYS, MAX_GROUPS, has_opposites, keys_text, valid_group_name

MSG_NAME_CHARS = "Group names can only use letters, numbers, - and _ (no spaces)."
MSG_NAME_DUPLICATE = "A group with that name already exists."
MSG_FROM_AFTER_TO = "From must not be after To."
MSG_GROUP_LIMIT = f"A project can hold up to {MAX_GROUPS} groups."
MSG_FRAME_LIMIT = "This is exceeding the frame limit."


class GroupError(ValueError):
    """The group cannot be saved; the message is the one to show the owner."""


class OverlapError(GroupError):
    """The frames already belong to another group (the panel offers 'Copy into new group')."""


def msg_overlap(first: int, last: int, other: str) -> str:
    return f"Frames {first} to {last} already belong to group {other}. Groups cannot overlap."


def msg_move_key(key: str, owner: str, new: str) -> str:
    return f"Move key {key} from {owner} to {new}?"


def msg_delete_group(name: str) -> str:
    return f"Delete group {name}? Its frames stay in the timeline."


def msg_rules_reset(name: str, affected: list[str]) -> str:
    return f"These rules pointed to {name} and have been reset: {', '.join(affected)}."


def find_group(project: Project, name: str) -> Group | None:
    return next((g for g in project.groups if g.name == name), None)


def key_owner(project: Project, key: str | None, ignore: str | None = None) -> str | None:
    """The group that already uses this key (not counting the group named `ignore`)."""
    if not key:
        return None
    return next((g.name for g in project.groups if g.key == key and g.name != ignore), None)


def check_group(project: Project, editing: str | None, name: str, first: int, last: int) -> None:
    """Raise GroupError if the group cannot be saved. `editing` is the name of the group being
    edited, or None for a new group. Frame numbers are 0-based."""
    if not valid_group_name(name):
        raise GroupError(MSG_NAME_CHARS)
    if any(g.name.lower() == name.lower() and g.name != editing for g in project.groups):
        raise GroupError(MSG_NAME_DUPLICATE)
    if editing is None and len(project.groups) >= MAX_GROUPS:
        raise GroupError(MSG_GROUP_LIMIT)
    if first > last:
        raise GroupError(MSG_FROM_AFTER_TO)
    if not (0 <= first and last < len(project.frames)):
        raise GroupError("The frames are outside the timeline.")
    for g in project.groups:
        if g.name == editing:
            continue
        lo, hi = max(first, g.first), min(last, g.last)
        if lo <= hi:
            raise OverlapError(msg_overlap(lo + 1, hi + 1, g.name))


def save_group(project: Project, editing: str | None, name: str, first: int, last: int,
               key: str | None, on_release: Rule | None, colour: Colour) -> Group:
    """Create or update a group (after check_group). A key already used elsewhere is taken away
    from the other group: the caller asks the owner first (msg_move_key)."""
    check_group(project, editing, name, first, last)
    if key is not None and key not in KEYS:
        raise GroupError("Unknown key.")
    owner = key_owner(project, key, ignore=editing)
    if owner is not None:
        find_group(project, owner).key = None
    if editing is None:
        group = Group(name, first, last, key, on_release, colour)
        project.groups.append(group)
        project.groups.sort(key=lambda g: g.first)
    else:
        group = find_group(project, editing)
        if group is None:
            raise GroupError("That group no longer exists.")
        if editing != name:                                  # other rules follow the new name
            for rule in _rules(project):
                if rule.kind == "group" and rule.target == editing:
                    rule.target = name
        if editing != name:
            for cr in project.control_rules:
                if cr.group == editing:
                    cr.group = name
                cr.only_in = [name if x == editing else x for x in cr.only_in]
            for t in project.transitions:
                t.from_groups = [name if x == editing else x for x in t.from_groups]
                if t.to == editing:
                    t.to = name
                if t.play == editing:
                    t.play = name
        group.name, group.first, group.last = name, first, last
        group.key, group.on_release, group.colour = key, on_release, colour
        if on_release is not None and on_release.kind == "group" and on_release.target == editing:
            on_release.target = name                      # a rule pointing to itself follows the rename
        project.groups.sort(key=lambda g: g.first)
    project.dirty = True
    return group


def _rules(project: Project):
    for g in project.groups:
        if g.on_release is not None:
            yield g.on_release
    for cr in project.control_rules:
        if cr.release is not None:
            yield cr.release
    if project.start_state is not None:
        yield project.start_state


def set_start_state(project: Project, rule: Rule | None) -> None:
    project.start_state = rule
    project.dirty = True


def rules_pointing_to(project: Project, name: str) -> list[str]:
    """Describe every rule that points to group `name`, for the rules-reset message."""
    out = [f"group {g.name} (On Release)" for g in project.groups
           if g.name != name                       # the deleted group's own rule goes with it
           and g.on_release is not None and g.on_release.kind == "group" and g.on_release.target == name]
    out += [f"rule {keys_text(cr.keys)} (Frame Group Control)" for cr in project.control_rules if cr.group == name]
    out += [f"rule {keys_text(cr.keys)} (Only if in)" for cr in project.control_rules
            if cr.group != name and name in cr.only_in]
    out += [f"transition {', '.join(t.from_groups) or 'Any'} to {t.to}" for t in project.transitions
            if name in (t.to, t.play) or name in t.from_groups]
    out += [f"rule {keys_text(cr.keys)} (When released)" for cr in project.control_rules
            if cr.group != name and cr.release is not None and cr.release.kind == "group" and cr.release.target == name]
    if project.start_state is not None and project.start_state.kind == "group" and project.start_state.target == name:
        out.append("Start state")
    return out


# ---- Frame Group Control rules (the keys that play a group) ----------------------------------------------------
MSG_RULE_NO_KEYS = "A rule needs at least one key."
MSG_RULE_NO_GROUP = "Choose a group for the rule."
MSG_RULE_ACTION_ALONE = "An action key (7, 8, 9, 0) cannot be combined with any other key."
MSG_RULE_OPPOSITE = "A joystick cannot press opposite directions (W and S, or A and D) together."
MSG_TRANSITION_GROUPS = "Choose the group to go to and the group to play first."
MSG_TRANSITION_SAME = "The group that plays first must be a different group from the one it goes to."


def check_transition(project: Project, t: Transition) -> None:
    """Raise GroupError if the transition cannot be kept."""
    if find_group(project, t.to) is None or find_group(project, t.play) is None:
        raise GroupError(MSG_TRANSITION_GROUPS)
    if t.play == t.to:
        raise GroupError(MSG_TRANSITION_SAME)
    if any(find_group(project, x) is None for x in t.from_groups):
        raise GroupError(MSG_TRANSITION_GROUPS)


def set_transitions(project: Project, transitions: list[Transition]) -> None:
    for t in transitions:
        check_transition(project, t)
    project.transitions = list(transitions)
    project.dirty = True


def check_control_rule(project: Project, rule: ControlRule) -> None:
    """Raise GroupError if the rule cannot be kept."""
    if not rule.keys:
        raise GroupError(MSG_RULE_NO_KEYS)
    if any(k not in ("W", "A", "S", "D", "1", "2", "3", "4", "5", "6") + ACTION_KEYS for k in rule.keys) or len(set(rule.keys)) != len(rule.keys):
        raise GroupError("Unknown key.")
    if any(k in ACTION_KEYS for k in rule.keys) and len(rule.keys) > 1:
        raise GroupError(MSG_RULE_ACTION_ALONE)
    if has_opposites(rule.keys):
        raise GroupError(MSG_RULE_OPPOSITE)
    if find_group(project, rule.group) is None:
        raise GroupError(MSG_RULE_NO_GROUP)
    if any(find_group(project, x) is None for x in rule.only_in):
        raise GroupError(MSG_RULE_NO_GROUP)


def set_control_rules(project: Project, rules: list[ControlRule]) -> None:
    for r in rules:
        check_control_rule(project, r)
    project.control_rules = list(rules)
    project.dirty = True


def set_group_key(project: Project, name: str, key: str | None) -> None:
    """The basic key of a group (shown in the Frame Group Control window as a 'from the panel' row). A key another group
    uses is taken from it: the caller asks first (msg_move_key)."""
    g = find_group(project, name)
    if g is None:
        raise GroupError("That group no longer exists.")
    if key is not None and key not in KEYS:
        raise GroupError("Unknown key.")
    owner = key_owner(project, key, ignore=name)
    if owner is not None:
        find_group(project, owner).key = None
    g.key = key
    project.dirty = True


def set_group_release(project: Project, name: str, rule: Rule | None) -> None:
    g = find_group(project, name)
    if g is None:
        raise GroupError("That group no longer exists.")
    g.on_release = rule
    project.dirty = True


def control_rules_for(project: Project, name: str) -> list[ControlRule]:
    return [cr for cr in project.control_rules if cr.group == name]
