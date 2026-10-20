"""Frame Group Control (v2.0.9): the window that says which keys play which frame group.

It lists the Frame Group Control rules (IF these keys are held THEN play this group), checked from the top with the first
match winning, and under them the basic key of each group (the key set in Set Frame Group before this window existed).
Every change is applied at once and is one Undo step. The controller picture lights the keys held while RunSpriteRun runs."""
from __future__ import annotations

import copy

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from src.app import messages
from src.app.common import frame_choice_text
from src.app.controller import Controller
from src.app.theme import short_popup
from src.core.project import ControlRule, Project, Rule
from src.core.rules import DIAGONALS, KEY_LABELS, buttons_for, key_available, keys_for, keys_text

HEADING = "color: #9aa0ae; font-size: 10px; font-weight: 700;"
WORD = "color: #ffd24d; font-weight: 700;"
GREY = "color: #9aa0ae;"
ROW = "QFrame#row { background: #25272e; border: 1px solid #3e414a; border-radius: 6px; }"
KEYS_BUTTON = ("QPushButton { background: #3780cd; border: 1px solid #78b9ff; border-radius: 5px; color: #ffffff; "
               "font-weight: 600; padding: 3px 10px; } QPushButton:hover { background: #4a90dd; }")
ICON_BUTTON = "QPushButton { padding: 2px 6px; min-width: 18px; }"
HELD_FILL, HELD_EDGE = QColor("#3780cd"), QColor("#ffd24d")
KEY_FILL, KEY_EDGE = QColor("#25272e"), QColor("#4a4e5a")

MSG_NO_GROUPS = "Create a frame group first. Rules choose which group plays."
SNES_NAMES = {"1": "1", "2": "2", "3": "3", "4": "4", "5": "L", "6": "R"}      # the SNES shoulder buttons are 5 and 6


class ControllerPad(QWidget):
    """The controller of the system: the 8 directions and its fire buttons. Display only: keys held while running light up."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(380, 178)
        self.system = ""
        self.held: set[str] = set()
        self.setAccessibleName("Controller")

    def set_system(self, system: str) -> None:
        self.system = system
        self.update()

    def set_held(self, keys) -> None:
        self.held = set(keys)
        self.update()

    def _key(self, p: QPainter, rect: QRectF, label: str, key: str, round_: bool = False) -> None:
        on = key in self.held
        p.setPen(QPen(HELD_EDGE if on else KEY_EDGE, 2 if on else 1))
        p.setBrush(HELD_FILL if on else KEY_FILL)
        if round_:
            p.drawEllipse(rect)
        else:
            p.drawRoundedRect(rect, 5, 5)
        p.setPen(QColor("#ffffff") if on else QColor("#c9ccd6"))
        p.drawText(rect, Qt.AlignCenter, label)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont(self.font())
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        cx, cy, s = 80, 90, 44
        for key, (dx, dy) in {"W": (0, -1), "S": (0, 1), "A": (-1, 0), "D": (1, 0), "W+A": (-1, -1), "W+D": (1, -1),
                              "S+A": (-1, 1), "S+D": (1, 1)}.items():
            self._key(p, QRectF(cx + dx * s - 19, cy + dy * s - 19, 38, 38), key, key)
        p.setPen(QPen(KEY_EDGE, 1))
        p.setBrush(QColor("#1c1d22"))
        p.drawRoundedRect(QRectF(cx - 19, cy - 19, 38, 38), 5, 5)
        n = buttons_for(self.system)
        if n == 6:                                                  # SNES: four face buttons in a diamond, two shoulder buttons above
            for key, (x, y) in {"1": (310, 100), "2": (272, 126), "3": (272, 74), "4": (234, 100)}.items():
                self._key(p, QRectF(x - 18, y - 18, 36, 36), SNES_NAMES[key], key, True)
            self._key(p, QRectF(215, 14, 70, 26), "L (5)", "5")
            self._key(p, QRectF(295, 14, 70, 26), "R (6)", "6")
        else:
            for i in range(n):
                self._key(p, QRectF(225 + i * 50, 118 - i * 14, 38, 38), str(i + 1), str(i + 1), True)


class KeysDialog(QDialog):
    """Choose the keys of a rule: click each key that must be held together."""

    def __init__(self, parent: QWidget, system: str, keys: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keys held")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Click every key that must be held together."))
        grid = QGridLayout()
        self.buttons: dict[str, QPushButton] = {}
        order = keys_for(system)
        for i, k in enumerate(order):
            b = QPushButton(SNES_NAMES.get(k, k) if buttons_for(system) == 6 and k.isdigit() else k)
            b.setCheckable(True)
            b.setChecked(k in keys)
            b.setMinimumSize(48, 34)
            self.buttons[k] = b
            grid.addWidget(b, 0 if i < 4 else 1, i if i < 4 else i - 4)
        lay.addLayout(grid)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self._ok)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _ok(self) -> None:
        if not self.keys():
            messages.warn(self, "Choose at least one key.")
            return
        self.accept()

    def keys(self) -> list[str]:
        return [k for k, b in self.buttons.items() if b.isChecked()]


class ReleaseChoice(QWidget):
    """What happens when all keys are let go: a short list of choices, with the frame or group to go to."""

    def __init__(self, project: Project, rule: Rule | None, none_text: str, on_change) -> None:
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.mode = QComboBox()
        self.mode.addItems([none_text, "Go To Frame", "Go to Group"])
        self.frame = QComboBox()
        self.group = QComboBox()
        short_popup(self.frame)
        short_popup(self.group)
        for i, f in enumerate(project.frames):
            self.frame.addItem(frame_choice_text(i, f.label), f.label)
        for g in project.groups:
            self.group.addItem(g.name, g.name)
        self.loop = QCheckBox("Loop")
        for w in (self.mode, self.frame, self.group, self.loop):
            lay.addWidget(w)
        lay.addStretch(1)
        if rule is not None and rule.kind == "frame" and self.frame.findData(rule.target) >= 0:
            self.mode.setCurrentIndex(1)
            self.frame.setCurrentIndex(self.frame.findData(rule.target))
        elif rule is not None and rule.kind == "group" and self.group.findData(rule.target) >= 0:
            self.mode.setCurrentIndex(2)
            self.group.setCurrentIndex(self.group.findData(rule.target))
            self.loop.setChecked(rule.loop)
        self._show()
        self.mode.currentIndexChanged.connect(lambda _i: (self._show(), on_change()))
        self.frame.currentIndexChanged.connect(lambda _i: on_change())
        self.group.currentIndexChanged.connect(lambda _i: on_change())
        self.loop.toggled.connect(lambda _b: on_change())

    def _show(self) -> None:
        m = self.mode.currentIndex()
        self.frame.setVisible(m == 1)
        self.group.setVisible(m == 2)
        self.loop.setVisible(m == 2)

    def rule(self) -> Rule | None:
        m = self.mode.currentIndex()
        if m == 1 and self.frame.count():
            return Rule("frame", self.frame.currentData())
        if m == 2 and self.group.count():
            return Rule("group", self.group.currentData(), self.loop.isChecked())
        return None


class ControlWindow(QDialog):
    """The Frame Group Control window. It stays open beside the main window (it is not modal)."""

    def __init__(self, parent: QWidget, controller: Controller) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Frame Group Control")
        self.setModal(False)
        self.resize(900, 640)
        self.setMinimumSize(760, 480)
        self._pending = False
        lay = QVBoxLayout(self)
        title = QLabel("Frame Group Control")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        lay.addWidget(title)
        self.subtitle = QLabel()
        self.subtitle.setStyleSheet(GREY)
        lay.addWidget(self.subtitle)
        top = QHBoxLayout()
        self.pad = ControllerPad()
        top.addWidget(self.pad)
        self.caption = QLabel("The keys you hold while RunSpriteRun runs light up here.\n"
                              "Rules are checked from the top. The first rule whose keys are all held plays its group.")
        self.caption.setWordWrap(True)
        self.caption.setStyleSheet(GREY)
        top.addWidget(self.caption, 1)
        lay.addLayout(top)
        head = QHBoxLayout()
        h = QLabel("RULES")
        h.setStyleSheet(HEADING)
        head.addWidget(h)
        head.addStretch(1)
        self.add_btn = QPushButton("+ Add rule")
        self.add_btn.clicked.connect(self._add_rule)
        head.addWidget(self.add_btn)
        lay.addLayout(head)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        lay.addWidget(self.scroll, 1)
        self.holder = QWidget()
        self.rows = QVBoxLayout(self.holder)
        self.rows.setContentsMargins(0, 0, 8, 0)
        self.rows.setSpacing(6)
        self.scroll.setWidget(self.holder)

        controller.project_changed.connect(self._later)
        controller.frames_changed.connect(self._later)
        controller.keys_held.connect(self.pad.set_held)
        controller.add_mode_changed.connect(self._enable)
        controller.edit.changed.connect(self._enable)
        self.rebuild()

    # ---- state ----------------------------------------------------------------------------------
    def _enable(self, *_args) -> None:
        self.setEnabled(not self.controller.add_mode and not self.controller.edit.mode)

    def _later(self, *_args) -> None:
        """Rebuild after the signal that asked for it has finished (a row must not be deleted while its own signal is running)."""
        if not self._pending:
            self._pending = True
            QTimer.singleShot(0, self._rebuild_now)

    def _rebuild_now(self) -> None:
        self._pending = False
        self.rebuild()

    @property
    def project(self) -> Project | None:
        return self.controller.project

    def rebuild(self) -> None:
        self._rc: dict[int, ReleaseChoice] = {}
        self._from: dict[int, QComboBox] = {}
        self._key_rc: dict[str, ReleaseChoice] = {}
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        p = self.project
        self.add_btn.setEnabled(p is not None)
        if p is None:
            self.subtitle.setText("No project open")
            return
        self.pad.set_system(p.system.name)
        n = buttons_for(p.system.name)
        self.subtitle.setText(f"{p.name}  ·  {p.system.name} controller: 8 directions and {n} fire button{'s' if n != 1 else ''}")
        for i in range(len(p.control_rules)):
            self.rows.addWidget(self._rule_row(i))
        if not p.control_rules:
            hint = QLabel("No rules yet. Use + Add rule, for example W+D held plays WalkUpRight, or W+D+1 plays a shot.")
            hint.setStyleSheet(GREY)
            hint.setWordWrap(True)
            self.rows.addWidget(hint)
        keyed = sorted((g for g in p.groups if g.key), key=lambda g: 0 if g.key in DIAGONALS else 1)
        head = QLabel("GROUP KEYS  (the key of each group, set here; they apply after the rules above. "
                      "A diagonal beats a single key, otherwise the key pressed last wins)")
        head.setStyleSheet(HEADING)
        head.setWordWrap(True)
        self.rows.addSpacing(8)
        self.rows.addWidget(head)
        for g in keyed:
            self.rows.addWidget(self._key_row(g.name))
        if not keyed:
            none = QLabel("No group has a key of its own.")
            none.setStyleSheet(GREY)
            self.rows.addWidget(none)
        self.rows.addStretch(1)
        self._enable()

    # ---- rows -----------------------------------------------------------------------------------
    def _row_frame(self) -> tuple[QFrame, QVBoxLayout]:
        row = QFrame()
        row.setObjectName("row")
        row.setStyleSheet(ROW)
        v = QVBoxLayout(row)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)
        return row, v

    def _group_combo(self, current: str) -> QComboBox:
        c = QComboBox()
        short_popup(c)
        for g in self.project.groups:
            c.addItem(g.name, g.name)
        c.setCurrentIndex(max(0, c.findData(current)))
        return c

    def _rule_row(self, i: int) -> QWidget:
        p = self.project
        r = p.control_rules[i]
        row, v = self._row_frame()
        line = QHBoxLayout()
        word = QLabel("IF" if i == 0 else "ELSE IF")
        word.setStyleSheet(WORD)
        word.setMinimumWidth(56)
        line.addWidget(word)
        keys = QPushButton(keys_text(r.keys))
        keys.setStyleSheet(KEYS_BUTTON)
        keys.setToolTip("Click to choose the keys that must be held together")
        keys.clicked.connect(lambda _c=False, i=i: self._choose_keys(i))
        line.addWidget(keys)
        line.addWidget(QLabel("held   THEN play"))
        grp = self._group_combo(r.group)
        grp.currentIndexChanged.connect(lambda _x, i=i, c=grp: self._edit(i, group=c.currentData()))
        line.addWidget(grp)
        mode = QComboBox()
        mode.addItems(["Loop", "Play once"])
        mode.setCurrentIndex(1 if r.once else 0)
        mode.currentIndexChanged.connect(lambda _x, i=i, c=mode: self._edit(i, once=c.currentIndex() == 1))
        line.addWidget(mode)
        line.addStretch(1)
        for text, tip, fn, on in (("▲", "Move up", lambda _c=False, i=i: self._move(i, -1), i > 0),
                                  ("▼", "Move down", lambda _c=False, i=i: self._move(i, 1), i < len(p.control_rules) - 1),
                                  ("✕", "Delete rule", lambda _c=False, i=i: self._delete(i), True)):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setStyleSheet(ICON_BUTTON)
            b.setEnabled(on)
            b.clicked.connect(fn)
            line.addWidget(b)
        v.addLayout(line)
        cond = QHBoxLayout()
        clab = QLabel("Only after:")
        clab.setStyleSheet(GREY)
        cond.addWidget(clab)
        frm = QComboBox()
        short_popup(frm)
        frm.addItem("Any frame", "")
        for g in p.groups:
            frm.addItem(g.name, g.name)
        frm.setCurrentIndex(max(0, frm.findData(r.from_group)))
        frm.setToolTip("The rule only fires if Hercules, or whatever is on screen, is currently in this group. "
                       "Use it for turns: play TurnLeft only after WalkRight.")
        frm.currentIndexChanged.connect(lambda _x, i=i, c=frm: self._edit(i, from_group=c.currentData()))
        self._from[i] = frm
        cond.addWidget(frm)
        hint = QLabel("e.g. play TurnLeft only after WalkRight (the frame on screen is in that group)")
        hint.setStyleSheet(GREY)
        cond.addWidget(hint)
        cond.addStretch(1)
        v.addLayout(cond)
        second = QHBoxLayout()
        lab = QLabel("When all keys are released:")
        lab.setStyleSheet(GREY)
        second.addWidget(lab)
        rc = ReleaseChoice(p, r.release, "Use the group's On Release", lambda i=i: self._release_changed(i))
        self._rc[i] = rc
        second.addWidget(rc, 1)
        v.addLayout(second)
        return row

    def _key_row(self, name: str) -> QWidget:
        p = self.project
        g = next(x for x in p.groups if x.name == name)
        row, v = self._row_frame()
        line = QHBoxLayout()
        word = QLabel("KEY")
        word.setStyleSheet(WORD)
        word.setMinimumWidth(56)
        line.addWidget(word)
        key = QComboBox()
        key.addItem("None", None)
        options = list(keys_for(p.system.name)[:4]) + list(DIAGONALS) + [k for k in keys_for(p.system.name) if k.isdigit()]
        for k in options:
            key.addItem(KEY_LABELS.get(k, k), k)
        if not key_available(p.system.name, g.key):               # a button the system's controller does not have
            key.addItem(f"{g.key}  (not on this system's controller)", g.key)
        key.setCurrentIndex(max(0, key.findData(g.key)))
        key.currentIndexChanged.connect(lambda _x, n=name, c=key: self.controller.set_group_key(n, c.currentData()))
        line.addWidget(key)
        line.addWidget(QLabel("held   THEN play"))
        line.addWidget(QLabel(f"<b>{name}</b>"))
        loop = QLabel("Loop")
        loop.setStyleSheet(GREY)
        line.addWidget(loop)
        line.addStretch(1)
        v.addLayout(line)
        second = QHBoxLayout()
        lab = QLabel("When all keys are released:")
        lab.setStyleSheet(GREY)
        second.addWidget(lab)
        rc = ReleaseChoice(p, g.on_release, "Stay on the last frame",
                           lambda n=name: self.controller.set_group_release(n, self._key_rc[n].rule()))
        self._key_rc[name] = rc
        second.addWidget(rc, 1)
        v.addLayout(second)
        return row

    # ---- changes (each is one Undo step) ---------------------------------------------------------
    def _rules_copy(self) -> list[ControlRule]:
        return copy.deepcopy(self.project.control_rules)

    def _edit(self, i: int, **fields) -> None:
        rules = self._rules_copy()
        for k, val in fields.items():
            setattr(rules[i], k, val)
        self.controller.set_control_rules(rules)

    def _release_changed(self, i: int) -> None:
        self._edit(i, release=self._rc[i].rule())

    def _choose_keys(self, i: int) -> None:
        dlg = KeysDialog(self, self.project.system.name, list(self.project.control_rules[i].keys))
        if dlg.exec() == QDialog.Accepted:
            self._edit(i, keys=dlg.keys())

    def _move(self, i: int, delta: int) -> None:
        rules = self._rules_copy()
        j = i + delta
        if 0 <= j < len(rules):
            rules[i], rules[j] = rules[j], rules[i]
            self.controller.set_control_rules(rules)

    def _delete(self, i: int) -> None:
        rules = self._rules_copy()
        del rules[i]
        self.controller.set_control_rules(rules)

    def _add_rule(self) -> None:
        p = self.project
        if p is None:
            return
        if not p.groups:
            messages.warn(self, MSG_NO_GROUPS)
            return
        dlg = KeysDialog(self, p.system.name, [])
        if dlg.exec() != QDialog.Accepted:
            return
        rules = self._rules_copy()
        rules.insert(0, ControlRule(dlg.keys(), p.groups[0].name))      # a new rule goes to the top: more specific rules should come first
        self.controller.set_control_rules(rules)
