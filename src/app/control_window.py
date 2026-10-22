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
from src.core.project import ControlRule, Project, Rule, Transition
from src.core.rules import ACTION_KEYS, DIAGONALS, KEY_LABELS, OPPOSITE, buttons_for, key_available, keys_for, keys_text

HEADING = "color: #9aa0ae; font-size: 10px; font-weight: 700;"
WORD = "color: #ffd24d; font-weight: 700;"
GREY = "color: #9aa0ae;"
ROW = "QFrame#row { background: #25272e; border: 1px solid #3e414a; border-radius: 6px; }"
KEYS_BUTTON = ("QPushButton { background: #3780cd; border: 1px solid #78b9ff; border-radius: 5px; color: #ffffff; "
               "font-weight: 600; padding: 3px 10px; } QPushButton:hover { background: #4a90dd; }")
ICON_BUTTON = "QPushButton { padding: 2px 6px; min-width: 18px; }"
HELD_FILL, HELD_EDGE = QColor("#2e4838"), QColor("#6eaa7d")        # a held or chosen key: muted green fill and border
ACTION_AMBER = QColor("#d6a046")
KEY_FILL, KEY_EDGE = QColor("#25272e"), QColor("#4a4e5a")

MSG_NO_GROUPS = "Create a frame group first. Rules choose which group plays."
SNES_NAMES = {"1": "1", "2": "2", "3": "3", "4": "4", "5": "L", "6": "R"}      # the SNES shoulder buttons are 5 and 6


class ControllerPad(QWidget):
    """The controller of the system: the 8 directions and its fire buttons. Display only: keys held while running light up."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(380, 232)
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

    def _actions(self, p: QPainter) -> None:
        """The Action animations row: keys 7 8 9 0, played by the game rather than the controller."""
        p.setPen(QPen(QColor("#50566a"), 1))
        p.drawLine(10, 166, 190, 166)
        f = QFont(self.font())
        f.setPixelSize(10)
        f.setBold(True)
        p.setFont(f)
        p.setPen(ACTION_AMBER)
        p.drawText(QRectF(10, 168, 180, 14), Qt.AlignLeft | Qt.AlignVCenter, "ACTION ANIMATIONS")
        f.setPixelSize(12)
        p.setFont(f)
        for i, k in enumerate(ACTION_KEYS):
            rect = QRectF(14 + i * 46, 186, 36, 36)
            on = k in self.held
            p.setPen(QPen(ACTION_AMBER, 3 if on else 1.5))
            p.setBrush(QColor("#46381c") if on else KEY_FILL)
            p.drawEllipse(rect)
            p.setPen(QColor("#ffffff"))
            p.drawText(rect, Qt.AlignCenter, k)

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
        self._actions(p)


KEY_ON = ("QPushButton:checked { background: #2e4838; border: 2px solid #6eaa7d; color: #ffffff; }")
ACTION_ON = ("QPushButton { border: 1px solid #d6a046; border-radius: 17px; } "
             "QPushButton:checked { background: #46381c; border: 3px solid #d6a046; color: #ffffff; } "
             "QPushButton:disabled { border: 1px solid #5a4a2a; color: #7a7f8c; }")


class KeysDialog(QDialog):
    """Choose the keys of a rule: click each key that must be held together. The directions are laid out as a cross
    (W up, A left, D right, S down) with the four diagonals in the corners; the action keys 7 8 9 0 stand alone."""

    def __init__(self, parent: QWidget, system: str, keys: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keys held")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Click every key that must be held together."))
        grid = QGridLayout()
        grid.setSpacing(6)
        self.buttons: dict[str, QPushButton] = {}
        self.corners: dict[str, QPushButton] = {}

        def make(label: str, checked: bool, size=(54, 40)) -> QPushButton:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setChecked(checked)
            b.setFixedSize(*size)
            b.setStyleSheet(KEY_ON)
            return b

        for k, (r, c) in {"W": (0, 1), "A": (1, 0), "D": (1, 2), "S": (2, 1)}.items():
            self.buttons[k] = make(k, k in keys)
            grid.addWidget(self.buttons[k], r, c)
        for name, (r, c) in {"W+A": (0, 0), "W+D": (0, 2), "S+A": (2, 0), "S+D": (2, 2)}.items():
            b = make("+", all(p in keys for p in DIAGONALS[name]))
            self.corners[name] = b
            b.toggled.connect(lambda on, name=name: self._corner(name, on))
            grid.addWidget(b, r, c)
        cross = QHBoxLayout()
        cross.addStretch(1)
        cross.addLayout(grid)
        cross.addStretch(1)
        lay.addLayout(cross)
        row = QHBoxLayout()
        row.addStretch(1)
        for k in keys_for(system)[4:]:
            b = make(SNES_NAMES.get(k, k) if buttons_for(system) == 6 else k, k in keys, (36, 36))
            b.setStyleSheet("QPushButton { border: 1px solid #6a7080; border-radius: 18px; } " + KEY_ON + " QPushButton:disabled { border: 1px solid #3a3e4a; color: #7a7f8c; }")
            self.buttons[k] = b
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        sep = QLabel("ACTION ANIMATIONS  (choose one; it cannot be combined with any other key)")
        sep.setStyleSheet("color: #d6a046; font-size: 10px; font-weight: bold; border-top: 1px solid #50566a; padding-top: 4px;")
        lay.addWidget(sep)
        arow = QHBoxLayout()
        arow.addStretch(1)
        for k in ACTION_KEYS:
            b = make(k, k in keys, (34, 34))
            b.setStyleSheet(ACTION_ON)
            self.buttons[k] = b
            arow.addWidget(b)
        arow.addStretch(1)
        lay.addLayout(arow)
        note = QLabel("A joystick cannot press opposite directions together: when A is chosen D is not available, and so on.")
        note.setWordWrap(True)
        note.setStyleSheet(GREY)
        lay.addWidget(note)
        for k, b in self.buttons.items():
            b.toggled.connect(lambda _on, k=k: self._changed(k))
        self._guard = False
        self._changed(None)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self._ok)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

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


class ReleaseChoice(QWidget):
    """What happens when all keys are let go: a short list of choices, with the frame or group to go to."""
    MODES = ("frame", "loop", "once", "still")

    def __init__(self, project: Project, rule: Rule | None, none_text: str, on_change) -> None:
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.mode = QComboBox()
        self.mode.addItems([none_text, "Go To Frame", "Go to Group (loop)", "Go to Group (play once)", "Go to Group (first frame only)"])
        self.frame = QComboBox()
        self.group = QComboBox()
        short_popup(self.frame)
        short_popup(self.group)
        for i, f in enumerate(project.frames):
            self.frame.addItem(frame_choice_text(i, f.label), f.label)
        for g in project.groups:
            self.group.addItem(g.name, g.name)
        for w in (self.mode, self.frame, self.group):
            lay.addWidget(w)
        lay.addStretch(1)
        if rule is not None and rule.kind == "frame" and self.frame.findData(rule.target) >= 0:
            self.mode.setCurrentIndex(1)
            self.frame.setCurrentIndex(self.frame.findData(rule.target))
        elif rule is not None and rule.kind == "group" and self.group.findData(rule.target) >= 0:
            self.mode.setCurrentIndex(2 if rule.loop else 3 if rule.once else 4)
            self.group.setCurrentIndex(self.group.findData(rule.target))
        self._show()
        self.mode.currentIndexChanged.connect(lambda _i: (self._show(), on_change()))
        self.frame.currentIndexChanged.connect(lambda _i: on_change())
        self.group.currentIndexChanged.connect(lambda _i: on_change())

    def _show(self) -> None:
        m = self.mode.currentIndex()
        self.frame.setVisible(m == 1)
        self.group.setVisible(m >= 2)

    def rule(self) -> Rule | None:
        m = self.mode.currentIndex()
        if m == 1 and self.frame.count():
            return Rule("frame", self.frame.currentData())
        if m >= 2 and self.group.count():
            return Rule("group", self.group.currentData(), m == 2, m == 3)
        return None


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
    return ", ".join(names) if names else empty


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
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
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
        foot = QHBoxLayout()
        note = QLabel("Changes take effect straight away. Press Apply to close this window.")
        note.setStyleSheet(GREY)
        foot.addWidget(note)
        foot.addStretch(1)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setStyleSheet(KEYS_BUTTON)
        self.apply_btn.setDefault(False)
        self.apply_btn.setAutoDefault(False)
        self.apply_btn.setMinimumWidth(110)
        self.apply_btn.clicked.connect(self._apply)
        foot.addWidget(self.apply_btn)
        lay.addLayout(foot)

        controller.project_changed.connect(self._later)
        controller.frames_changed.connect(self._later)
        controller.keys_held.connect(self.pad.set_held)
        controller.add_mode_changed.connect(self._enable)
        controller.edit.changed.connect(self._enable)
        self.rebuild()

    # ---- closing: Apply, Esc and the X all do the same: close (changes are already applied) ------------
    def _apply(self) -> None:
        self.hide()

    def reject(self) -> None:                       # Esc
        self._apply()

    def closeEvent(self, event) -> None:            # the X in the title bar
        event.accept()

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
        self._from: dict[int, QPushButton] = {}
        self._tr: dict[int, dict] = {}
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
        self._transition_section(p)
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
        clab = QLabel("Only if in:")
        clab.setStyleSheet(GREY)
        cond.addWidget(clab)
        frm = QPushButton(groups_text(r.only_in, "Any frame") + "  ▾")
        frm.setToolTip("The rule only fires while the frame on screen is in one of these groups. Tick every group in which the character "
                       "faces the same way, for example IdleLeft, WalkLeft and CrouchLeft for a FireLeft rule.")
        frm.clicked.connect(lambda _c=False, i=i: self._pick_only_in(i))
        self._from[i] = frm
        cond.addWidget(frm)
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

    # ---- transitions ----------------------------------------------------------------------------
    def _transition_section(self, p: Project) -> None:
        head = QHBoxLayout()
        h = QLabel("TRANSITIONS")
        h.setStyleSheet(HEADING)
        head.addWidget(h)
        sub = QLabel("going from one group to another, play a group once first (it has no key of its own)")
        sub.setStyleSheet(GREY)
        head.addWidget(sub, 1)
        self.add_tr_btn = QPushButton("+ Add transition")
        self.add_tr_btn.clicked.connect(self._add_transition)
        head.addWidget(self.add_tr_btn)
        wrap = QWidget()
        wrap.setLayout(head)
        self.rows.addSpacing(8)
        self.rows.addWidget(wrap)
        for i, t in enumerate(p.transitions):
            self.rows.addWidget(self._transition_row(i, t))
        if not p.transitions:
            hint = QLabel("No transitions. With none, a group starts straight away. Example: going from WalkRight to WalkLeft plays TurnLeft "
                          "once first. A row naming a group beats a row for any group.")
            hint.setStyleSheet(GREY)
            hint.setWordWrap(True)
            self.rows.addWidget(hint)

    def _transition_row(self, i: int, t: Transition) -> QWidget:
        p = self.project
        row, v = self._row_frame()
        line = QHBoxLayout()
        word = QLabel("FROM")
        word.setStyleSheet(WORD)
        word.setMinimumWidth(56)
        line.addWidget(word)
        frm = QPushButton(groups_text(t.from_groups, "Any group") + "  ▾")
        frm.setToolTip("Click to tick the groups this applies to; none ticked means any group")
        frm.clicked.connect(lambda _c=False, i=i: self._pick_from(i))
        line.addWidget(frm)
        line.addWidget(QLabel("  going TO"))
        to = self._group_combo(t.to)
        to.currentIndexChanged.connect(lambda _x, i=i, c=to: self._edit_transition(i, to=c.currentData()))
        line.addWidget(to)
        line.addWidget(QLabel("  play first (once)"))
        play = self._group_combo(t.play)
        play.currentIndexChanged.connect(lambda _x, i=i, c=play: self._edit_transition(i, play=c.currentData()))
        line.addWidget(play)
        irq = QCheckBox("Can be interrupted")
        irq.setChecked(t.interruptible)
        irq.setToolTip("Off: it always plays through. On: a change of keys while it plays stops it at once.")
        irq.toggled.connect(lambda on, i=i: self._edit_transition(i, interruptible=bool(on)))
        line.addWidget(irq)
        line.addStretch(1)
        b = QPushButton("✕")
        b.setToolTip("Delete transition")
        b.setStyleSheet(ICON_BUTTON)
        b.clicked.connect(lambda _c=False, i=i: self._delete_transition(i))
        line.addWidget(b)
        v.addLayout(line)
        self._tr[i] = {"from": frm, "to": to, "play": play, "interruptible": irq}
        return row

    def _transitions_copy(self) -> list[Transition]:
        return copy.deepcopy(self.project.transitions)

    def _edit_transition(self, i: int, **fields) -> None:
        ts = self._transitions_copy()
        for k, val in fields.items():
            setattr(ts[i], k, val)
        self.controller.set_transitions(ts)

    def _pick_from(self, i: int) -> None:
        names = [g.name for g in self.project.groups]
        dlg = GroupsPicker(self, names, list(self.project.transitions[i].from_groups), "From groups",
                           "Tick the groups the character may be in. Tick none for any group.")
        if dlg.exec() == QDialog.Accepted:
            self._edit_transition(i, from_groups=dlg.chosen())

    def _delete_transition(self, i: int) -> None:
        ts = self._transitions_copy()
        del ts[i]
        self.controller.set_transitions(ts)

    def _add_transition(self) -> None:
        p = self.project
        if p is None:
            return
        if len(p.groups) < 2:
            messages.warn(self, "Create at least two frame groups first. A transition goes to one group and plays another first.")
            return
        ts = self._transitions_copy()
        ts.append(Transition([], p.groups[0].name, p.groups[1].name))
        self.controller.set_transitions(ts)

    def _pick_only_in(self, i: int) -> None:
        names = [g.name for g in self.project.groups]
        dlg = GroupsPicker(self, names, list(self.project.control_rules[i].only_in), "Only if in",
                           "The rule only fires while the frame on screen is in one of the ticked groups. Tick none for any frame.")
        if dlg.exec() == QDialog.Accepted:
            self._edit(i, only_in=dlg.chosen())

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
