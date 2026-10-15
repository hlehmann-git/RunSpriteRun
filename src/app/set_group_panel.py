"""Set Frame Group panel (FR-3.11): create, edit and rename a group. Nothing changes until Apply."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QComboBox, QFrame, QLabel, QLineEdit, QPushButton, QSpinBox, QWidget

from src.app.theme import short_popup
from src.app import messages
from src.app.controller import Controller
from src.app.panel import Panel
from src.app.rule_editor import RuleEditor
from src.app.sprite_view import SpriteView
from src.core import edit, groups
from src.core.project import Rule
from src.core.rules import GROUP_NAME_MAX, KEY_LABELS, KEYS, MAX_GROUPS

NEW_GROUP = "New group"
GREY = "color: #9aa0ae;"
HEADING = "color: #9aa0ae; font-size: 10px; font-weight: 700;"
APPLY_STYLE = ("QPushButton { background: #3780cd; border: 1px solid #78b9ff; border-radius: 5px; color: #ffffff; "
               "font-weight: 600; } QPushButton:hover { background: #4a90dd; } QPushButton:pressed { background: #2c68a8; } "
               "QPushButton:disabled { background: #30323a; border: 1px solid #45474f; color: #78787f; }")


class SetFrameGroupPanel(Panel):
    current_group_changed = Signal(object)        # name of the group being edited, or None for a new one

    def __init__(self, parent: QWidget, controller: Controller) -> None:
        super().__init__("Set Frame Group", parent)
        self.controller = controller
        self.current: str | None = None
        self.blank = True                # no group to show: the panel is empty and greyed out
        self._colour = QColor(0, 0, 0)

        # Layout (v2): header row, then two columns separated by a thin line.
        #   left: GROUP (name, colour) and FRAMES (from / to with thumbnails); right: ON HOLD KEY and ON RELEASE
        self.chooser = QComboBox(self)
        short_popup(self.chooser)
        self.chooser.setGeometry(161, 9, 150, 26)
        self._line(17, 41, 508, 1)
        self._line(285, 53, 1, 138)

        self._heading("GROUP", 17, 50)
        self._row_label("Name", 17, 64, 50)
        self.name = QLineEdit(self)
        self.name.setGeometry(69, 64, 200, 26)
        self.name.setMaxLength(GROUP_NAME_MAX)
        self._row_label("Colour", 17, 96, 50)
        self.colour_btn = QPushButton(self)
        self.colour_btn.setGeometry(69, 96, 56, 26)
        self.colour_hint = self._row_label("click to change", 137, 96, 110)
        self.colour_hint.setStyleSheet("color: #9aa0ae; font-size: 11px;")

        self._heading("FRAMES", 17, 133)
        self.from_view = SpriteView(self, grid=False, size=36)
        self.to_view = SpriteView(self, grid=False, size=36)
        self.from_box = QSpinBox(self)
        self.to_box = QSpinBox(self)
        for b in (self.from_box, self.to_box):
            b.setButtonSymbols(QSpinBox.NoButtons)
            b.setFixedSize(46, 26)
        self._row_label("From", 17, 156, 36)
        self.from_box.move(55, 156)
        self.from_view.move(107, 151)
        self._row_label("To", 161, 156, 24)
        self.to_box.move(183, 156)
        self.to_view.move(235, 151)

        self._heading("ON HOLD KEY", 299, 50)
        self.key = QComboBox(self)
        for k in KEYS:
            self.key.addItem(KEY_LABELS.get(k, k), k)     # shown as "W+A (up-left)", kept as "W+A"
        self.key.addItem("None", None)
        self.key.setGeometry(299, 64, 126, 26)
        self.will_loop = self._row_label("Will loop", 437, 64, 80)
        self.will_loop.setStyleSheet(GREY)
        self.release_label = self._heading("ON RELEASE", 299, 99)
        self.release = RuleEditor(self)
        self.release.compact()
        self.release.move(299, 114)
        self.apply_btn = QPushButton("Apply", self)
        self.apply_btn.setGeometry(447, 175, 80, 26)
        self.apply_btn.setDefault(True)
        self.apply_btn.setStyleSheet(APPLY_STYLE)

        self.chooser.activated.connect(self._chosen)
        self.from_box.valueChanged.connect(self._thumbs)
        self.to_box.valueChanged.connect(self._thumbs)
        self.key.currentTextChanged.connect(self._key_changed)
        self.colour_btn.clicked.connect(self._pick_colour)
        self.apply_btn.clicked.connect(self.apply)
        controller.project_changed.connect(self._project_changed)
        controller.frames_changed.connect(self.refresh)
        controller.selection_changed.connect(self._selection_changed)

    def _label(self, text: str, x: int, y: int) -> QLabel:
        lab = QLabel(text, self)
        lab.move(x, y)
        lab.adjustSize()
        return lab

    def _row_label(self, text: str, x: int, y: int, w: int) -> QLabel:
        """A label vertically centred on a 26 px high control row."""
        lab = QLabel(text, self)
        lab.setGeometry(x, y, w, 26)
        lab.setStyleSheet(GREY if text != "Will loop" else "")
        return lab

    def _heading(self, text: str, x: int, y: int) -> QLabel:
        lab = QLabel(text, self)
        lab.setStyleSheet(HEADING)
        lab.setGeometry(x, y, 150, 14)
        return lab

    def _line(self, x: int, y: int, w: int, h: int) -> None:
        f = QFrame(self)
        f.setGeometry(x, y, w, h)
        f.setStyleSheet("background: #3e414a; border: none;")

    # ---- showing the model ---------------------------------------------------------------------
    def _project_changed(self) -> None:
        self.current = None
        self.blank = True
        self._follow_selection()
        self.refresh()

    def _selection_changed(self, _index: int) -> None:
        """Selecting a frame shows its group; a frame outside every group empties the panel."""
        self._follow_selection()
        self.refresh()

    def _follow_selection(self) -> None:
        p = self.controller.project
        if p is None:
            return
        name = edit.group_of_frame(p)[self.controller.selected]
        if name is not None:
            self.current, self.blank = name, False
        elif self.current is not None or self.blank:         # a group or the empty panel was showing
            self.current, self.blank = None, True
        # else: "New group" is being filled in; it stays, From/To follow the frame

    def refresh(self) -> None:
        p = self.controller.project
        names = [g.name for g in p.groups] if p else []
        if self.current not in names:
            self.current = None
        self.chooser.blockSignals(True)
        self.chooser.clear()
        self.chooser.addItem(NEW_GROUP)
        self.chooser.addItems(names)
        if self.blank:
            self.chooser.setCurrentIndex(-1)
        else:
            self.chooser.setCurrentIndex(0 if self.current is None else names.index(self.current) + 1)
        self.chooser.blockSignals(False)
        if p is not None:
            n = len(p.frames)
            for b in (self.from_box, self.to_box):
                b.blockSignals(True)
                b.setRange(1, max(1, n))
                b.blockSignals(False)
        self._load()

    def _chosen(self, index: int) -> None:
        self.current = None if index == 0 else self.chooser.itemText(index)
        self.blank = False
        self._load()

    def new_group(self) -> None:
        """Group > New Group: show an empty panel; the group is created when Apply is clicked."""
        self.current = None
        self.blank = False
        self.refresh()

    def _load(self) -> None:
        p = self.controller.project
        if p is None:
            self.current_group_changed.emit(None)
            return
        g = groups.find_group(p, self.current) if self.current else None
        sel = self.controller.selected
        self._show_blank(self.blank)
        if self.blank:
            self.current_group_changed.emit(None)
            return
        self.name.setText(g.name if g else "")
        for b, v in ((self.from_box, (g.first if g else sel) + 1), (self.to_box, (g.last if g else sel) + 1)):
            b.blockSignals(True)
            b.setValue(v)
            b.blockSignals(False)
        self.key.blockSignals(True)
        self.key.setCurrentIndex(self.key.findData(g.key if g and g.key else None))
        self.key.blockSignals(False)
        self._set_colour(QColor(*(g.colour if g else (0, 0, 0))))
        default = Rule("frame", p.frames[0].label)                  # a new group starts at Go To Frame 1
        self.release.load(p, g.on_release if g else default)
        self._key_changed()
        self._thumbs()
        self.current_group_changed.emit(self.current)

    def _show_blank(self, blank: bool) -> None:
        """Empty, greyed-out panel for a frame that is in no group."""
        for w in (self.name, self.from_box, self.to_box, self.key, self.release, self.colour_btn, self.apply_btn):
            w.setEnabled(not blank)
        self.release.setVisible(not blank)
        self.release_label.setVisible(not blank)
        self.colour_hint.setVisible(not blank)
        self.from_view.setVisible(not blank)
        self.to_view.setVisible(not blank)
        self.will_loop.setVisible(not blank and self.key.currentData() is not None)
        for b in (self.from_box, self.to_box):
            b.blockSignals(True)
            b.setSpecialValueText(" " if blank else "")
            b.setMinimum(0 if blank else 1)
            if blank:
                b.setValue(0)
            b.blockSignals(False)
        if blank:
            self.name.setText("")
            self.key.blockSignals(True)
            self.key.setCurrentIndex(self.key.findData(None))
            self.key.blockSignals(False)
            self._set_colour(QColor(0, 0, 0))
            self.colour_btn.setStyleSheet("background: #1e1f24; border: 1px solid #3a3d47; border-radius: 4px;")

    def _thumbs(self) -> None:
        p = self.controller.project
        if p is None or not p.frames:
            return
        for box, view in ((self.from_box, self.from_view), (self.to_box, self.to_view)):
            view.set_sprite(p.frames[min(box.value(), len(p.frames)) - 1].image, p.transparent)

    def _key_changed(self) -> None:
        self.will_loop.setVisible(self.key.currentData() is not None)

    def _set_colour(self, c: QColor) -> None:
        self._colour = c
        self.colour_btn.setStyleSheet(f"background: {c.name()}; border: 1px solid #8a8a94; border-radius: 4px;")

    def _pick_colour(self) -> None:
        c = QColorDialog.getColor(self._colour, self, "Group Colour")
        if c.isValid():
            self._set_colour(c)

    def _copy_into_new_group(self) -> bool:
        key = self.key.currentData()
        c = self._colour
        return self.controller.copy_into_new_group(self.name.text(), self.from_box.value() - 1,
                                                   self.to_box.value() - 1, key, self.release.rule(),
                                                   (c.red(), c.green(), c.blue()))

    # ---- Apply ----------------------------------------------------------------------------------
    def apply(self) -> bool:
        p = self.controller.project
        if p is None:
            return False
        name = self.name.text()
        first, last = self.from_box.value() - 1, self.to_box.value() - 1
        key = self.key.currentData()
        parent = self.controller.parent_widget
        try:
            before = self.controller.checkpoint()
            groups.check_group(p, self.current, name, first, last)
            owner = groups.key_owner(p, key, ignore=self.current)
            if owner is not None and not messages.choose(parent, groups.msg_move_key(key, owner, name),
                                                         "", "Move", "Cancel"):
                return False
            groups.save_group(p, self.current, name, first, last, key, self.release.rule(),
                              (self._colour.red(), self._colour.green(), self._colour.blue()))
        except groups.OverlapError as e:
            if self.current is None and messages.overlap(parent, str(e)):
                return self._copy_into_new_group()
            if self.current is not None:
                messages.warn(parent, str(e))
            return False
        except groups.GroupError as e:
            messages.warn(parent, str(e))
            return False
        self.current = name
        self.controller.commit(before)
        self.controller.frames_changed.emit()
        return True
