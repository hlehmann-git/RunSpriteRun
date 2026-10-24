"""Frame Group Control (v2.0.14): the pop-up that says which keys play which frame group.

Rules read as one sentence each, "Holding W + 1 plays ShootRight Loop only if in Right groups release Frame 1", numbered
from the top (the first rule that matches wins). Transitions read "Going from A to B play C first".
The window edits a copy: Apply saves it as one Undo step, Cancel (or Esc, or the X) throws the changes away.
Keys 7 8 9 0 are action keys: they play a group on their own for testing, and that group is used by nothing else."""
from __future__ import annotations

import copy

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QBoxLayout, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from src.app import messages
from src.app.common import frame_choice_text
from src.app.controller import Controller
from src.app.theme import short_popup
from src.core import groups
from src.core.project import ControlRule, Project, Rule, Transition
from src.core.rules import ACTION_KEYS, DIAGONALS, KEY_LABELS, OPPOSITE, buttons_for, key_available, keys_for

HEADING = "color: #9aa0ae; font-size: 10px; font-weight: 700;"
NUMBER = "color: #d6a046; font-weight: 700;"
GREY = "color: #9aa0ae;"
RED = "color: #ff7b72; font-size: 11px;"
ROW = "QFrame#row { background: #25272e; border: 1px solid #3e414a; border-radius: 6px; }"
ROW_BAD = "QFrame#row { background: #2e2326; border: 1px solid #b5524a; border-radius: 6px; }"
KEYS_BUTTON = ("QPushButton { background: #3780cd; border: 1px solid #78b9ff; border-radius: 5px; color: #ffffff; "
               "font-weight: 600; padding: 3px 10px; } QPushButton:hover { background: #4a90dd; }")
ICON_BUTTON = "QPushButton { padding: 2px 6px; min-width: 18px; }"
APPLY_BUTTON = KEYS_BUTTON + " QPushButton:disabled { background: #3a3e4a; border: 1px solid #50566a; color: #7a7f8c; }"
INFO = "color: #9aa0ae; border: 1px solid #6a7080; border-radius: 7px; font-size: 9px; font-weight: 700; min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px; qproperty-alignment: AlignCenter;"
WRAP_WIDTH = 960                                    # narrower than this, a rule goes onto two lines

MSG_NO_GROUPS = "Create a frame group first. Rules choose which group plays."
MSG_NO_FREE_GROUP = "Every group is already used on the other side. Action keys play a group that no other rule or transition uses."
SNES_NAMES = {"1": "1", "2": "2", "3": "3", "4": "4", "5": "L", "6": "R"}      # the SNES shoulder buttons are 5 and 6
TIPS = {
    "rules": "Rules are checked from the top. The first rule whose keys are all held plays its group. Put a rule with more keys "
             "(W + 1) above a rule with fewer (W).",
    "transitions": "Going from one group to another, play a group once first. With none, the new group starts straight away.",
}


def info_label(tip: str) -> QLabel:
    lab = QLabel("i")
    lab.setStyleSheet(INFO)
    lab.setToolTip(tip)
    lab.setAlignment(Qt.AlignCenter)
    return lab


def chip_text(keys) -> str:
    from src.core.rules import keys_text
    return " + ".join(keys_text(keys).split("+"))


KEY_ON = "QPushButton:checked { background: #2e4838; border: 2px solid #6eaa7d; color: #ffffff; }"
FIRE = "QPushButton { border: 1px solid #6a7080; border-radius: 16px; } "
ACTION_ON = FIRE + "QPushButton:checked { background: #54421f; border: 2px solid #d6a046; color: #ffffff; }"


class KeysDialog(QDialog):
    """Choose the keys of a rule: click each key that must be held together. The directions are laid out as a cross
    (W up, A left, D right, S down) with the four diagonals in the corners; the action keys 7 8 9 0 stand alone."""

    def __init__(self, parent: QWidget, system: str, keys: list[str], title: str = "Keys held") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(6)
        head = QLabel(title)
        head.setStyleSheet("font-size: 13px; font-weight: 700;")
        lay.addWidget(head)
        hint = QLabel("Click keys to add or remove them.")
        hint.setStyleSheet(GREY)
        lay.addWidget(hint)
        grid = QGridLayout()
        grid.setSpacing(8)
        self.buttons: dict[str, QPushButton] = {}
        self.corners: dict[str, QPushButton] = {}

        def make(label: str, checked: bool, size=(32, 24)) -> QPushButton:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setChecked(checked)
            b.setFixedSize(*size)
            b.setStyleSheet(KEY_ON)
            return b

        for k, (r, c) in {"W": (0, 1), "A": (1, 0), "D": (1, 2), "S": (2, 1)}.items():
            self.buttons[k] = make(k, k in keys)
            grid.addWidget(self.buttons[k], r, c, Qt.AlignCenter)
        for name, (r, c) in {"W+A": (0, 0), "W+D": (0, 2), "S+A": (2, 0), "S+D": (2, 2)}.items():
            b = make("+", all(p in keys for p in DIAGONALS[name]), (24, 20))
            self.corners[name] = b
            b.toggled.connect(lambda on, name=name: self._corner(name, on))
            grid.addWidget(b, r, c, Qt.AlignCenter)
        cross = QHBoxLayout()
        cross.addStretch(1)
        cross.addLayout(grid)
        cross.addStretch(1)
        lay.addLayout(cross)
        lab = QLabel("BUTTONS")
        lab.setStyleSheet(HEADING)
        lay.addWidget(lab)
        row = QHBoxLayout()
        row.setSpacing(12)
        for k in keys_for(system)[4:]:
            b = make(SNES_NAMES.get(k, k) if buttons_for(system) == 6 else k, k in keys, (32, 32))
            b.setStyleSheet(FIRE + KEY_ON + " QPushButton:disabled { border: 1px solid #3a3e4a; color: #7a7f8c; }")
            self.buttons[k] = b
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        sep = QLabel("ACTION ANIMATIONS")
        sep.setStyleSheet("color: #d6a046; font-size: 9px; font-weight: bold; border-top: 1px solid #3e414a; padding-top: 6px;")
        lay.addWidget(sep)
        arow = QHBoxLayout()
        arow.setSpacing(12)
        for k in ACTION_KEYS:
            b = make(k, k in keys, (32, 32))
            b.setStyleSheet(ACTION_ON + " QPushButton:disabled { border: 1px solid #3a3e4a; color: #7a7f8c; }")
            self.buttons[k] = b
            arow.addWidget(b)
        arow.addStretch(1)
        lay.addLayout(arow)
        for k, b in self.buttons.items():
            b.toggled.connect(lambda _on, k=k: self._changed(k))
        self._guard = False
        self._changed(None)
        foot = QHBoxLayout()
        uses = QLabel("Uses")
        uses.setStyleSheet(GREY)
        foot.addWidget(uses)
        self.preview = QLabel()
        self.preview.setStyleSheet("background: #3780cd; border-radius: 5px; color: #ffffff; font-weight: 700; padding: 3px 8px;")
        foot.addWidget(self.preview)
        foot.addStretch(1)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self._ok)
        box.rejected.connect(self.reject)
        foot.addWidget(box)
        lay.addLayout(foot)
        self._preview()

    def _preview(self) -> None:
        keys = self.keys()
        self.preview.setText(chip_text(keys) if keys else "no key")

    def _corner(self, name: str, on: bool) -> None:
        """A corner "+" picks (or lets go of) both of its directions."""
        if self._guard:
            return
        self._guard = True
        for k in DIAGONALS[name]:
            self.buttons[k].setChecked(on)
        self._guard = False
        self._changed(None)

    def _changed(self, key) -> None:
        if self._guard:
            return
        self._guard = True
        if key in ACTION_KEYS and self.buttons[key].isChecked():        # an action key stands alone
            for k, b in self.buttons.items():
                if k != key:
                    b.setChecked(False)
        elif key is not None and self.buttons[key].isChecked():          # choosing a normal key lets go of any action key
            for k in ACTION_KEYS:
                self.buttons[k].setChecked(False)
        for name, b in self.corners.items():
            b.setChecked(all(self.buttons[p].isChecked() for p in DIAGONALS[name]))
        self._guard = False
        self._opposites()
        if hasattr(self, "preview"):
            self._preview()

    def _opposites(self) -> None:
        """A key whose opposite is chosen cannot be chosen; a chosen action key greys out everything else."""
        action = next((k for k in ACTION_KEYS if self.buttons[k].isChecked()), None)
        for k, b in self.buttons.items():
            o = OPPOSITE.get(k)
            b.setEnabled(action in (None, k) and not (o is not None and self.buttons[o].isChecked()))
        for name, b in self.corners.items():
            b.setEnabled(action is None and all(self.buttons[p].isEnabled() or self.buttons[p].isChecked()
                                                for p in DIAGONALS[name]))

    def _ok(self) -> None:
        if not self.keys():
            messages.warn(self, "Choose at least one key.")
            return
        self.accept()

    def keys(self) -> list[str]:
        order = ("W", "A", "S", "D") + tuple(str(n) for n in range(1, 7)) + ACTION_KEYS
        return [k for k in order if k in self.buttons and self.buttons[k].isChecked()]


class ReleaseChoice(QComboBox):
    """What happens when all keys are let go, in one drop-down: the group's own choice, a frame, or a group.
    An action key offers only the frames of its own group."""

    def __init__(self, project: Project, rule: Rule | None, none_text: str, on_change, only_frames_of: str | None = None) -> None:
        super().__init__()
        short_popup(self, 12)
        self.addItem(none_text, None)
        labels = groups.group_frame_labels(project, only_frames_of) if only_frames_of is not None else None
        for i, f in enumerate(project.frames):
            if labels is None or f.label in labels:
                self.addItem(frame_choice_text(i, f.label), self.key_of(Rule("frame", f.label)))
        if only_frames_of is None:
            for g in project.groups:
                self.addItem(f"Group {g.name} (loop)", self.key_of(Rule("group", g.name, True, False)))
                self.addItem(f"Group {g.name} (once)", self.key_of(Rule("group", g.name, False, True)))
                self.addItem(f"Group {g.name} (first frame)", self.key_of(Rule("group", g.name, False, False)))
        if rule is not None:
            data = self.key_of(rule)
            i = self.findData(data)
            if i < 0:                                      # points somewhere not offered: show it so the problem is visible
                self.addItem(f"{rule.target} (not allowed here)", data)
                i = self.count() - 1
            self.setCurrentIndex(i)
        self.currentIndexChanged.connect(lambda _i: on_change())

    @staticmethod
    def key_of(rule: Rule) -> str:
        return f"frame|{rule.target}" if rule.kind == "frame" else f"group|{rule.target}|{int(rule.loop)}|{int(rule.once)}"

    def rule(self) -> Rule | None:
        d = self.currentData()
        if d is None:
            return None
        kind, target, *flags = d.split("|")
        return Rule("frame", target) if kind == "frame" else Rule("group", target, flags[0] == "1", flags[1] == "1")


class GroupsPicker(QDialog):
    """Tick the groups for a condition or a transition (none ticked = any group, where that is allowed)."""

    def __init__(self, parent: QWidget, names: list[str], chosen: list[str], title: str, hint: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        lay = QVBoxLayout(self)
        lbl = QLabel(hint)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(GREY)
        lay.addWidget(lbl)
        self.boxes: dict[str, QCheckBox] = {}
        for n in names:
            b = QCheckBox(n)
            b.setChecked(n in chosen)
            self.boxes[n] = b
            lay.addWidget(b)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def chosen(self) -> list[str]:
        return [n for n, b in self.boxes.items() if b.isChecked()]


def groups_text(names: list[str], empty: str) -> str:
    """A short summary of a list of groups for a button: Any, the name, or how many."""
    if not names:
        return empty
    return names[0] if len(names) == 1 else f"{names[0]}, {len(names) - 1} more"


class GroupKeysDialog(QDialog):
    """Older projects can have a group with a key of its own (the group plays while that key is held, after the rules). Those
    keys and their On Release choices are edited here. The changes go into the Frame Group Control window's copy (`draft`:
    group name -> [key, on_release]) and count only when that window's Apply is pressed; its Cancel drops them."""

    def __init__(self, parent: QWidget, controller: Controller, draft: dict | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Group keys")
        lay = QVBoxLayout(self)
        note = QLabel("A group with a key of its own plays while that key is held, after the rules in Frame Group Control. "
                      "Changes here are kept when you press Apply in Frame Group Control.")
        note.setWordWrap(True)
        note.setStyleSheet(GREY)
        lay.addWidget(note)
        p = controller.project
        if draft is None:
            draft = getattr(parent, "d_keys", None)
            if draft is None:
                draft = {g.name: [g.key, copy.deepcopy(g.on_release)] for g in p.groups if g.key}
        self.draft = draft
        self._rc: dict[str, ReleaseChoice] = {}
        self._key_boxes: dict[str, QComboBox] = {}
        by_name = {g.name: g for g in p.groups}
        names = [n for n in draft if n in by_name]
        for name in sorted(names, key=lambda n: 0 if draft[n][0] in DIAGONALS else 1):
            key_now, release_now = draft[name]
            line = QHBoxLayout()
            key = QComboBox()
            key.addItem("None", None)
            for k in list(keys_for(p.system.name)[:4]) + list(DIAGONALS) + [k for k in keys_for(p.system.name) if k.isdigit()]:
                key.addItem(KEY_LABELS.get(k, k), k)
            if key_now and not key_available(p.system.name, key_now):
                key.addItem(f"{key_now}  (not on this system's controller)", key_now)
            key.setCurrentIndex(max(0, key.findData(key_now)))
            key.currentIndexChanged.connect(lambda _x, n=name, c=key: self._set_key(n, c))
            self._key_boxes[name] = key
            line.addWidget(key)
            line.addWidget(QLabel(f"held plays <b>{name}</b>, on release"))
            rc = ReleaseChoice(p, release_now, "Stay on last frame", lambda: None)
            rc.currentIndexChanged.connect(lambda _x, n=name: self._set_release(n))
            self._rc[name] = rc
            line.addWidget(rc)
            lay.addLayout(line)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        lay.addWidget(close, 0, Qt.AlignRight)

    def _set_key(self, name: str, box: QComboBox) -> None:
        key = box.currentData()
        owner = next((n for n, (k, _r) in self.draft.items() if key and k == key and n != name), None)
        if owner is not None:
            if not messages.choose(self, groups.msg_move_key(key, owner, name), "", "Move", "Cancel"):
                box.blockSignals(True)
                box.setCurrentIndex(max(0, box.findData(self.draft[name][0])))
                box.blockSignals(False)
                return
            self.draft[owner][0] = None
            other = self._key_boxes.get(owner)
            if other is not None:
                other.blockSignals(True)
                other.setCurrentIndex(0)
                other.blockSignals(False)
        self.draft[name][0] = key

    def _set_release(self, name: str) -> None:
        self.draft[name][1] = self._rc[name].rule()


class ControlWindow(QDialog):
    """The Frame Group Control window. It is modal and edits a copy of the rules and transitions: Apply saves them as one
    Undo step; Cancel, Esc and the X in the title bar close it with no change."""

    def __init__(self, parent: QWidget, controller: Controller) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Frame Group Control")
        self.setModal(True)
        self.resize(1040, 640)
        self.setMinimumSize(700, 420)
        self.d_rules: list[ControlRule] = []
        self.d_trans: list[Transition] = []
        self._pending = False
        self._rows: dict[tuple[str, int], tuple[QFrame, QLabel]] = {}
        self._wrapping: list[QBoxLayout] = []
        lay = QVBoxLayout(self)
        title = QLabel("Frame Group Control")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        lay.addWidget(title)
        self.subtitle = QLabel()
        self.subtitle.setStyleSheet(GREY)
        lay.addWidget(self.subtitle)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        lay.addWidget(self.scroll, 1)
        self.holder = QWidget()
        self.rows = QVBoxLayout(self.holder)
        self.rows.setContentsMargins(0, 0, 8, 0)
        self.rows.setSpacing(6)
        self.scroll.setWidget(self.holder)
        foot = QHBoxLayout()
        self.note = QLabel()
        self.note.setStyleSheet(RED)
        foot.addWidget(self.note, 1)
        self.keys_btn = QPushButton("Group keys…")
        self.keys_btn.setToolTip("Older projects only: groups that have a key of their own")
        self.keys_btn.clicked.connect(self._group_keys)
        foot.addWidget(self.keys_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setAutoDefault(False)
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.clicked.connect(self.reject)
        foot.addWidget(self.cancel_btn)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setStyleSheet(APPLY_BUTTON)
        self.apply_btn.setAutoDefault(False)
        self.apply_btn.setMinimumWidth(110)
        self.apply_btn.clicked.connect(self._apply)
        foot.addWidget(self.apply_btn)
        lay.addLayout(foot)
        controller.project_changed.connect(lambda *_a: self.reject())      # a different project: nothing here applies to it

    # ---- opening and closing --------------------------------------------------------------------
    def load(self) -> None:
        """Start from the rules and transitions of the open project."""
        p = self.project
        self.d_rules = copy.deepcopy(p.control_rules) if p is not None else []
        self.d_trans = copy.deepcopy(p.transitions) if p is not None else []
        self.d_keys = ({g.name: [g.key, copy.deepcopy(g.on_release)] for g in p.groups if g.key}
                       if p is not None else {})                  # Group keys: changed only by Apply
        self.rebuild()

    def _group_keys(self) -> None:
        GroupKeysDialog(self, self.controller, self.d_keys).exec()

    def _apply(self) -> None:
        p = self.project
        if p is None or self._problems():
            return
        rules = copy.deepcopy(self.d_rules)
        for r in rules:
            if any(k in ACTION_KEYS for k in r.keys):
                r.once = True                                      # an action key plays its group once
        if self.controller.set_rules_and_transitions(rules, copy.deepcopy(self.d_trans), copy.deepcopy(self.d_keys)):
            self.accept()

    # ---- state ----------------------------------------------------------------------------------
    @property
    def project(self) -> Project | None:
        return self.controller.project

    def _problems(self) -> dict:
        p = self.project
        return groups.rule_problems(p, self.d_rules, self.d_trans) if p is not None else {}

    def _later(self) -> None:
        """Rebuild after the signal that asked for it has finished (a row must not be deleted while its own signal is running)."""
        if not self._pending:
            self._pending = True
            QTimer.singleShot(0, self._rebuild_now)

    def _rebuild_now(self) -> None:
        self._pending = False
        self.rebuild()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._wrap()

    def _wrap(self) -> None:
        d = QBoxLayout.TopToBottom if self.width() < WRAP_WIDTH else QBoxLayout.LeftToRight
        for lay in self._wrapping:
            lay.setDirection(d)

    def _mark(self) -> None:
        """Show what is wrong in red under each row and allow Apply only when nothing is."""
        bad = self._problems()
        for key, (row, note) in self._rows.items():
            msg = bad.get(key)
            row.setStyleSheet(ROW_BAD if msg else ROW)
            note.setText(msg or "")
            note.setVisible(bool(msg))
        self.apply_btn.setEnabled(not bad)
        self.note.setText("Fix the rows marked in red to apply." if bad else "")

    def rebuild(self) -> None:
        self._rows = {}
        self._wrapping = []
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        p = self.project
        if p is None:
            self.subtitle.setText("No project open")
            return
        self.keys_btn.setVisible(any(g.key for g in p.groups))      # only older projects have group keys
        n = buttons_for(p.system.name)
        self.subtitle.setText(f"{p.name}  ·  {p.system.name}: 8 directions and {n} fire button{'s' if n != 1 else ''}.   "
                              "Rules are checked from the top. Changes are saved when you press Apply.")
        self.rows.addWidget(self._heading("RULES", TIPS["rules"], "+ Add rule", self._add_rule))
        for i in range(len(self.d_rules)):
            self.rows.addWidget(self._rule_row(i))
        self.rows.addSpacing(10)
        self.rows.addWidget(self._heading("TRANSITIONS", TIPS["transitions"], "+ Add transition", self._add_transition))
        for i in range(len(self.d_trans)):
            self.rows.addWidget(self._transition_row(i))
        self.rows.addStretch(1)
        self._wrap()
        self._mark()

    def _heading(self, text: str, tip: str, add_text: str, add_fn) -> QWidget:
        w = QWidget()
        line = QHBoxLayout(w)
        line.setContentsMargins(0, 0, 0, 0)
        h = QLabel(text)
        h.setStyleSheet(HEADING)
        line.addWidget(h)
        line.addWidget(info_label(tip))
        line.addStretch(1)
        b = QPushButton(add_text)
        b.clicked.connect(lambda _c=False: add_fn())
        b.setEnabled(self.project is not None)
        line.addWidget(b)
        if text == "RULES":
            self.add_btn = b
        else:
            self.add_tr_btn = b
        return w

    # ---- rows -----------------------------------------------------------------------------------
    def _row_shell(self, key: tuple[str, int]) -> tuple[QFrame, QBoxLayout, QBoxLayout, QBoxLayout]:
        """A framed row: its sentence in two halves that sit side by side, or one above the other in a narrow window."""
        row = QFrame()
        row.setObjectName("row")
        row.setStyleSheet(ROW)
        v = QVBoxLayout(row)
        v.setContentsMargins(10, 6, 10, 6)
        v.setSpacing(2)
        both = QBoxLayout(QBoxLayout.LeftToRight)
        both.setSpacing(8)
        first, second = QHBoxLayout(), QHBoxLayout()
        first.setSpacing(6)
        second.setSpacing(6)
        both.addLayout(first)
        both.addLayout(second, 1)
        v.addLayout(both)
        note = QLabel()
        note.setStyleSheet(RED)
        note.setWordWrap(True)
        note.setVisible(False)
        v.addWidget(note)
        self._rows[key] = (row, note)
        self._wrapping.append(both)
        return row, first, second, both

    @staticmethod
    def _word(text: str, style: str = GREY) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet(style)
        return lab

    def _names(self, only: str) -> list[str]:
        """The groups a row may offer: "action" = groups no normal rule or transition uses; "control" = groups no action key plays."""
        action = groups.action_groups(self.d_rules)
        normal = {r.group for r in self.d_rules if not any(k in ACTION_KEYS for k in r.keys)}
        for t in self.d_trans:
            normal.update([t.to, t.play, *t.from_groups])
        for r in self.d_rules:
            normal.update(r.only_in)
        names = [g.name for g in self.project.groups]
        return [n for n in names if (n not in normal if only == "action" else n not in action)]

    def _group_combo(self, current: str, only: str) -> QComboBox:
        c = QComboBox()
        short_popup(c)
        names = self._names(only)
        if current not in names:
            names.append(current)
        for n in names:
            c.addItem(n, n)
        c.setCurrentIndex(max(0, c.findData(current)))
        return c

    def _rule_row(self, i: int) -> QWidget:
        p = self.project
        r = self.d_rules[i]
        is_action = any(k in ACTION_KEYS for k in r.keys)
        row, a, b, _both = self._row_shell(("rule", i))
        a.addWidget(self._word(f"{i + 1}", NUMBER))
        a.addWidget(self._word("Holding"))
        keys = QPushButton(chip_text(r.keys))
        keys.setStyleSheet(KEYS_BUTTON)
        keys.setToolTip("Click to choose the keys that must be held together")
        keys.clicked.connect(lambda _c=False, i=i: self._choose_keys(i))
        a.addWidget(keys)
        a.addWidget(self._word("plays"))
        grp = self._group_combo(r.group, "action" if is_action else "control")
        grp.currentIndexChanged.connect(lambda _x, i=i, c=grp: self._edit(i, group=c.currentData()))
        a.addWidget(grp)
        mode = QComboBox()
        mode.addItems(["Loop", "Once"])
        mode.setCurrentIndex(1 if (r.once or is_action) else 0)
        mode.setEnabled(not is_action)
        if is_action:
            mode.setToolTip("An action key plays its group once")
        mode.currentIndexChanged.connect(lambda _x, i=i, c=mode: self._edit(i, once=c.currentIndex() == 1))
        a.addWidget(mode)
        if not is_action:
            b.addWidget(self._word("only if in"))
            frm = QPushButton(groups_text(r.only_in, "Any") + "  ▾")
            frm.setToolTip("The rule only fires while the frame on screen is in one of these groups. Tick every group in which the "
                           "character faces the same way, for example IdleLeft, WalkLeft and CrouchLeft for a FireLeft rule.")
            frm.clicked.connect(lambda _c=False, i=i: self._pick_only_in(i))
            b.addWidget(frm)
        b.addWidget(self._word("release"))
        rc = ReleaseChoice(p, r.release, "Stay on last frame" if is_action else "Group default",
                           lambda i=i: None, only_frames_of=r.group if is_action else None)
        rc.currentIndexChanged.connect(lambda _x, i=i, c=rc: self._edit(i, release=c.rule()))
        b.addWidget(rc)
        b.addStretch(1)
        for text, tip, fn, on in (("▲", "Move up", lambda _c=False, i=i: self._move(i, -1), i > 0),
                                  ("▼", "Move down", lambda _c=False, i=i: self._move(i, 1), i < len(self.d_rules) - 1),
                                  ("✕", "Delete rule", lambda _c=False, i=i: self._delete(i), True)):
            btn = QPushButton(text)
            btn.setToolTip(tip)
            btn.setStyleSheet(ICON_BUTTON)
            btn.setEnabled(on)
            btn.clicked.connect(fn)
            b.addWidget(btn)
        return row

    def _transition_row(self, i: int) -> QWidget:
        t = self.d_trans[i]
        row, a, b, _both = self._row_shell(("transition", i))
        a.addWidget(self._word("Going from"))
        frm = QPushButton(groups_text(t.from_groups, "Any") + "  ▾")
        frm.setToolTip("Click to tick the groups this applies to; none ticked means any group")
        frm.clicked.connect(lambda _c=False, i=i: self._pick_from(i))
        a.addWidget(frm)
        a.addWidget(self._word("to"))
        to = self._group_combo(t.to, "control")
        to.currentIndexChanged.connect(lambda _x, i=i, c=to: self._edit_transition(i, to=c.currentData()))
        a.addWidget(to)
        b.addWidget(self._word("play"))
        play = self._group_combo(t.play, "control")
        play.currentIndexChanged.connect(lambda _x, i=i, c=play: self._edit_transition(i, play=c.currentData()))
        b.addWidget(play)
        b.addWidget(self._word("first"))
        irq = QCheckBox("Can be interrupted")
        irq.setChecked(t.interruptible)
        irq.setToolTip("Off: it always plays through. On: a change of keys while it plays stops it at once.")
        irq.toggled.connect(lambda on, i=i: self._edit_transition(i, interruptible=bool(on), rebuild=False))
        b.addWidget(irq)
        b.addStretch(1)
        x = QPushButton("✕")
        x.setToolTip("Delete transition")
        x.setStyleSheet(ICON_BUTTON)
        x.clicked.connect(lambda _c=False, i=i: self._delete_transition(i))
        b.addWidget(x)
        return row

    # ---- changes to the copy ----------------------------------------------------------------------
    def _edit(self, i: int, **fields) -> None:
        for k, val in fields.items():
            setattr(self.d_rules[i], k, val)
        self._later()

    def _edit_transition(self, i: int, rebuild: bool = True, **fields) -> None:
        for k, val in fields.items():
            setattr(self.d_trans[i], k, val)
        if rebuild:
            self._later()
        else:
            self._mark()

    def _pick_from(self, i: int) -> None:
        dlg = GroupsPicker(self, self._names("control"), list(self.d_trans[i].from_groups), "From groups",
                           "Tick the groups the character may be in. Tick none for any group.")
        if dlg.exec() == QDialog.Accepted:
            self._edit_transition(i, from_groups=dlg.chosen())

    def _pick_only_in(self, i: int) -> None:
        dlg = GroupsPicker(self, self._names("control"), list(self.d_rules[i].only_in), "Only if in",
                           "The rule only fires while the frame on screen is in one of the ticked groups. Tick none for any frame.")
        if dlg.exec() == QDialog.Accepted:
            self._edit(i, only_in=dlg.chosen())

    def _choose_keys(self, i: int) -> None:
        r = self.d_rules[i]
        dlg = KeysDialog(self, self.project.system.name, list(r.keys), f"Keys for rule {i + 1}")
        if dlg.exec() != QDialog.Accepted:
            return
        keys = dlg.keys()
        was_action = any(k in ACTION_KEYS for k in r.keys)
        now_action = any(k in ACTION_KEYS for k in keys)
        r.keys = keys
        if now_action and not was_action:
            r.once, r.release, r.only_in = True, None, []
        elif was_action and not now_action:
            r.release = None
        self._later()

    def _move(self, i: int, delta: int) -> None:
        j = i + delta
        if 0 <= j < len(self.d_rules):
            self.d_rules[i], self.d_rules[j] = self.d_rules[j], self.d_rules[i]
            self._later()

    def _delete(self, i: int) -> None:
        del self.d_rules[i]
        self._later()

    def _add_rule(self) -> None:
        p = self.project
        if p is None:
            return
        if not p.groups:
            messages.warn(self, MSG_NO_GROUPS)
            return
        dlg = KeysDialog(self, p.system.name, [], "Keys for the new rule")
        if dlg.exec() != QDialog.Accepted:
            return
        keys = dlg.keys()
        is_action = any(k in ACTION_KEYS for k in keys)
        free = self._names("action" if is_action else "control")
        if not free:
            messages.warn(self, MSG_NO_FREE_GROUP)
            return
        # a new rule goes to the top: more specific rules should come first
        self.d_rules.insert(0, ControlRule(keys, free[0], once=is_action))
        self._later()

    def _add_transition(self) -> None:
        p = self.project
        names = self._names("control")
        if p is None:
            return
        if len(names) < 2:
            messages.warn(self, "Create at least two frame groups first. A transition goes to one group and plays another first.")
            return
        self.d_trans.append(Transition([], names[0], names[1]))
        self._later()

    def _delete_transition(self, i: int) -> None:
        del self.d_trans[i]
        self._later()
