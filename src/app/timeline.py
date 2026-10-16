"""Timeline and frames panel (FR-3.2): 9 frame boxes visible at once, a scroll bar and arrows,
Frame number / Frame Label / Frame Group rows, selection, label editing, and reordering by
dragging or Ctrl+Left / Ctrl+Right."""
from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QPolygonF, QShortcut
from PySide6.QtWidgets import QLabel, QLineEdit, QMenu, QScrollBar, QToolButton, QWidget

from src.app.controller import Controller
from src.app.keys_panel import KeyPad
from src.app.paste_frame_dialog import PasteFrameDialog
from src.app.panel import Panel
from src.app.theme import SCROLLBAR_STYLE
from src.app.render import scaled_sprite, to_qimage
from src.core.edit import group_of_frame
from src.core.rules import LABEL_MAX

VISIBLE = 8
BOX_W, BOX_H, PITCH = 112, 112, 118       # a frame box and the distance between boxes
FIRST_X = 272                            # left edge of the first box in the panel
THUMB_Y = 42
ROW_H = 16
NUMBER_Y, LABEL_Y, GROUP_Y = 158, 178, 198
DRAG_START = 6                           # pixels the pointer must move before a drag begins

BORDER = QColor(0x3A, 0x3D, 0x47)
SELECTED_BG = QColor(0x3A, 0x42, 0x54)
NORMAL_BG = QColor(0x1E, 0x1F, 0x24)
EDITING = QColor(0xFF, 0x98, 0x28)       # border of the frame being edited
PLAYING = QColor(0xFF, 0xD2, 0x4D)      # border of the frame a playing view is showing


class Thumb(QWidget):
    """One frame box: the sprite at the largest whole-number scale that fits, in a 1 px border."""
    pressed = Signal(int)
    dragged = Signal(int, QPoint)        # slot, pointer position in the timeline panel
    released = Signal(int, QPoint)
    menu_requested = Signal(int, QPoint)  # slot, screen position (right click)

    def __init__(self, parent: QWidget, slot: int) -> None:
        super().__init__(parent)
        self.slot = slot
        self.setFixedSize(BOX_W, BOX_H)
        self.image = None
        self.transparent = (0, 0, 0)
        self.border = BORDER
        self.selected = False
        self.playing = False
        self.editing = False                 # Edit mode: the frame being edited (orange line inside its group border)
        self._press: QPoint | None = None
        self._dragging = False

    def set_frame(self, image, transparent, border: QColor, selected: bool, playing: bool = False,
                  editing: bool = False) -> None:
        self.image, self.transparent, self.border, self.selected = image, transparent, border, selected
        self.playing = playing
        self.editing = editing
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), SELECTED_BG if self.selected else NORMAL_BG)
        if self.image is not None:
            dpr = self.devicePixelRatioF()
            inner_w, inner_h = round((BOX_W - 4) * dpr), round((BOX_H - 4) * dpr)
            img = self.image
            shrink = max(-(-img.width // inner_w), -(-img.height // inner_h))     # frames bigger than the box: whole-number shrink
            if shrink > 1:
                img = img.resize((max(1, img.width // shrink), max(1, img.height // shrink)), Image.NEAREST)
            sprite = scaled_sprite(img, self.transparent, inner_w, inner_h, grid=False, hide=True)
            qimg = to_qimage(sprite, dpr)
            x = (BOX_W - sprite.width / dpr) / 2
            y = (BOX_H - sprite.height / dpr) / 2
            p.drawImage(int(x), int(y), qimg)
        p.setPen(QPen(self.border, 1))
        p.drawRect(0, 0, BOX_W - 1, BOX_H - 1)
        if self.playing:
            p.setPen(QPen(PLAYING, 2))
            p.drawRect(1, 1, BOX_W - 3, BOX_H - 3)
        if self.editing:                                  # the group colour border stays; an orange bar marks this frame
            p.fillRect(1, BOX_H - 6, BOX_W - 2, 5, EDITING)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._press, self._dragging = e.position().toPoint(), False
            self.pressed.emit(self.slot)

    def contextMenuEvent(self, e) -> None:
        self.menu_requested.emit(self.slot, e.globalPos())

    def mouseMoveEvent(self, e) -> None:
        if self._press is None:
            return
        pos = e.position().toPoint()
        if not self._dragging and (pos - self._press).manhattanLength() > DRAG_START:
            self._dragging = True
        if self._dragging:
            self.dragged.emit(self.slot, self.mapTo(self.parentWidget().parentWidget(), pos))

    def mouseReleaseEvent(self, e) -> None:
        if self._press is not None and self._dragging:
            self.released.emit(self.slot, self.mapTo(self.parentWidget().parentWidget(), e.position().toPoint()))
        self._press, self._dragging = None, False


class Slot(QWidget):
    """The widgets for one visible frame: box, number, label (editable) and group (read-only)."""

    def __init__(self, parent: QWidget, slot: int) -> None:
        super().__init__(parent)
        self.slot = slot
        self.copied = False
        self.setGeometry(FIRST_X + slot * PITCH, 0, BOX_W, 220)
        self.thumb = Thumb(self, slot)
        self.thumb.move(0, THUMB_Y)
        self.number = self._cell(NUMBER_Y)
        self.group = self._cell(GROUP_Y)
        self.label = QLineEdit(self)
        self.label.setGeometry(0, LABEL_Y, BOX_W, ROW_H)
        self.label.setMaxLength(LABEL_MAX)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(self._style(True))

    def _cell(self, y: int) -> QLabel:
        lab = QLabel(self)
        lab.setGeometry(0, y, BOX_W, ROW_H)
        lab.setAlignment(Qt.AlignCenter)
        lab.setStyleSheet(self._style(False))
        return lab

    @staticmethod
    def _style(editable: bool, copied: bool = False) -> str:
        bg = "#1e1f24" if editable else "#23252b"
        colour = ""
        if copied:                                    # a copied frame that still needs its own label
            bg, colour = "#c0392b", " color:#ffffff;"
        return f"background:{bg};{colour} border:1px solid #3a3d47; border-radius:2px; padding:0; font-size:11px;"

    def set_copied(self, copied: bool) -> None:
        if copied != self.copied:
            self.copied = copied
            self.label.setStyleSheet(self._style(True, copied))


class ArrowButton(QToolButton):
    """A light grey triangle (left or right), larger than the standard arrow so it does not get lost in the dark UI."""

    def __init__(self, parent: QWidget, direction: int) -> None:
        super().__init__(parent)
        self.direction = direction                      # -1 left, +1 right
        self.setAutoRaise(True)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.isEnabled():
            colour = QColor("#ffffff") if self.underMouse() else QColor("#c8ccd8")
        else:
            colour = QColor("#4a4e5a")
        c, h, w = self.rect().center(), 11, 9
        tip, base = c.x() + self.direction * w // 2 + (1 if self.direction > 0 else -1), c.x() - self.direction * w // 2
        p.setPen(Qt.NoPen)
        p.setBrush(colour)
        p.drawPolygon(QPolygonF([QPointF(tip, c.y()), QPointF(base, c.y() - h), QPointF(base, c.y() + h)]))


class TimelinePanel(Panel):
    def __init__(self, parent: QWidget, controller: Controller) -> None:
        super().__init__("Timeline and frames", parent)
        self.controller = controller
        self.first = 0                       # index of the first visible frame
        self.slots = [Slot(self, i) for i in range(VISIBLE)]
        for s in self.slots:
            s.thumb.pressed.connect(lambda slot: self._click(slot))
            s.thumb.dragged.connect(self._drag_move)
            s.thumb.released.connect(self._drag_end)
            s.thumb.menu_requested.connect(self._menu)
            s.label.editingFinished.connect(lambda s=s: self._label_done(s))
        for i, (text, y) in enumerate((("Frame number", NUMBER_Y), ("Frame Label", LABEL_Y), ("Frame Group", GROUP_Y))):
            lab = QLabel(text, self)
            lab.setGeometry(FIRST_X - 88, y, 82, ROW_H)
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lab.setStyleSheet("font-size:11px;")
        self.pad = KeyPad(self)                # FR-3.12: the keys held, drawn small at the left of the frames
        self.pad.move(14, THUMB_Y)
        self.pad.colour_of = self._key_colour
        controller.keys_held.connect(self.pad.set_held)
        controller.project_changed.connect(lambda: self.pad.set_held([]))
        for s in self.slots:
            s.label.installEventFilter(self)
        QApplication.instance().installEventFilter(self)
        self.left = ArrowButton(self, -1)
        self.right = ArrowButton(self, 1)
        for btn, x in ((self.left, FIRST_X - 30), (self.right, FIRST_X + VISIBLE * PITCH - 2)):
            btn.setGeometry(x, THUMB_Y + 36, 26, 40)
        self.left.clicked.connect(lambda: self.scroll_by(-1))
        self.right.clicked.connect(lambda: self.scroll_by(1))
        self.bar = QScrollBar(Qt.Horizontal, self)
        self.bar.setGeometry(FIRST_X, 220, VISIBLE * PITCH - 6, 12)
        self.bar.setStyleSheet(SCROLLBAR_STYLE)
        self.bar.valueChanged.connect(self._bar_moved)
        self.marker = QWidget(self)
        self.marker.setStyleSheet("background:#4da3ff;")
        self.marker.setFixedSize(3, BOX_H)
        self.marker.hide()
        self.playing = -1
        self.run_index = -1                  # frame shown by RunSpriteRun while it is running
        self._drag_src: int | None = None
        self._drag_gap: int | None = None
        QShortcut(QKeySequence("Ctrl+Left"), self, lambda: controller.move_selected(-1)).setContext(
            Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence("Ctrl+Right"), self, lambda: controller.move_selected(1)).setContext(
            Qt.WidgetWithChildrenShortcut)
        self.setFocusPolicy(Qt.ClickFocus)           # Ctrl+C / Ctrl+V work only while the last click was in this panel
        QShortcut(QKeySequence("Ctrl+C"), self, self._copy).setContext(Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence("Ctrl+V"), self, self._paste).setContext(Qt.WidgetWithChildrenShortcut)
        QApplication.instance().focusChanged.connect(self._focus_changed)
        controller.project_changed.connect(self._project_changed)
        controller.frames_changed.connect(self.refresh)
        controller.edit.changed.connect(self.refresh)
        controller.selection_changed.connect(self._selection_changed)
        controller.playing_frame.connect(self._playing_changed)
        controller.run_frame.connect(self._run_changed)
        controller.run_state.connect(lambda _on: self.refresh())

    # ---- ending a label edit (FR-3.2) --------------------------------------------------------
    def _editing_label(self):
        w = QApplication.focusWidget()
        return w if any(w is s.label for s in self.slots) else None

    def eventFilter(self, obj, event) -> bool:
        t = event.type()
        if t == QEvent.KeyPress and event.key() == Qt.Key_Escape and any(obj is s.label for s in self.slots):
            obj.clearFocus()                         # Esc ends the edit and keeps the text typed so far
            return True
        if t == QEvent.MouseButtonPress:
            label = self._editing_label()
            if label is not None and obj is not label and not self.isHidden():
                label.clearFocus()                   # a click anywhere outside the label box does the same
        return False

    # ---- model -> widgets -----------------------------------------------------------------
    def frame_count(self) -> int:
        p = self.controller.project
        return len(p.frames) if p else 0

    def _project_changed(self) -> None:
        self.first = 0
        self.refresh()

    def _playing_changed(self, index: int) -> None:
        self.playing = index
        self.refresh()

    def _run_changed(self, index: int) -> None:
        self.run_index = index
        self.refresh()

    def _selection_changed(self, index: int) -> None:
        if index < self.first:
            self.first = index
        elif index >= self.first + VISIBLE:
            self.first = index - VISIBLE + 1
        self.refresh()

    def refresh(self) -> None:
        p = self.controller.project
        n = self.frame_count()
        self.first = max(0, min(self.first, max(0, n - VISIBLE)))
        self.bar.blockSignals(True)
        self.bar.setRange(0, max(0, n - VISIBLE))
        self.bar.setPageStep(VISIBLE)
        self.bar.setValue(self.first)
        self.bar.blockSignals(False)
        groups = group_of_frame(p) if p else []
        colours = {g.name: QColor(*g.colour) for g in p.groups} if p else {}
        for k, s in enumerate(self.slots):
            i = self.first + k
            s.setVisible(i < n)
            if i >= n or p is None:
                continue
            frame = p.frames[i]
            g = groups[i]
            e = self.controller.edit
            border = colours[g] if g else BORDER                 # always the group's own colour
            s.thumb.set_frame(frame.image, p.transparent, border, i == self.controller.selected,
                             i == self.playing or (self.controller.running and self.controller.runner.animating and i == self.run_index),
                             e.mode and i == e.idx)
            s.number.setText(str(i + 1))
            if s.label.text() != frame.label:
                s.label.setText(frame.label)
            s.group.setText(g or "")
            s.set_copied(frame.copied)
            s.label.setReadOnly(self.controller.edit.mode)      # no renaming while editing
        self.left.setEnabled(self.first > 0)
        self.right.setEnabled(self.first < n - VISIBLE)

    # ---- scrolling --------------------------------------------------------------------------
    def _key_colour(self, key: str):
        p = self.controller.project
        g = next((g for g in p.groups if g.key == key), None) if p else None
        return QColor(*g.colour) if g else None

    def scroll_by(self, delta: int) -> None:
        self.bar.setValue(self.first + delta)

    def _bar_moved(self, value: int) -> None:
        self.first = value
        self.refresh()

    def wheelEvent(self, e) -> None:
        self.scroll_by(-1 if e.angleDelta().y() > 0 else 1)

    # ---- user actions ------------------------------------------------------------------------
    def _click(self, slot: int) -> None:
        self.setFocus(Qt.MouseFocusReason)
        self.controller.select(self.first + slot)

    # ---- copy and paste a frame --------------------------------------------------------------
    def _focus_changed(self, old, new) -> None:
        """Clicking out of this panel drops a copied frame, silently."""
        if new is None or (new is not self and not self.isAncestorOf(new)):
            if self.controller.frame_clipboard is not None and not self._asking:
                self.controller.drop_frame_clipboard()

    _asking = False

    def _copy(self) -> None:
        if not self.controller.edit.mode:
            self.controller.copy_frame()

    def _paste(self) -> None:
        c = self.controller
        src = c.frame_clipboard
        if c.project is None or c.edit.mode or src is None:
            return                                   # nothing copied: do nothing
        self._asking = True                          # the question window takes the focus; keep the copied frame
        try:
            dlg = PasteFrameDialog(self, c.selected + 1, src.label)
            ok = dlg.exec()
        finally:
            self._asking = False
        if ok:
            c.paste_frame(dlg.paste_after(), src)

    def _exec_menu(self, menu: QMenu, pos: QPoint):
        return menu.exec(pos)

    def _menu(self, slot: int, pos: QPoint) -> None:
        i = self.first + slot
        c = self.controller
        if c.project is None or c.edit.mode or i >= self.frame_count():
            return
        self.setFocus(Qt.MouseFocusReason)
        c.select(i)
        menu = QMenu(self)
        before = menu.addAction("Copy before")
        after = menu.addAction("Copy after")
        self._asking = True
        try:
            chosen = self._exec_menu(menu, pos)
        finally:
            self._asking = False
        if chosen is before:
            c.clone_frame(i, False)
        elif chosen is after:
            c.clone_frame(i, True)

    def _label_done(self, s: Slot) -> None:
        i = self.first + s.slot
        if self.controller.project is None or i >= self.frame_count():
            return
        if not self.controller.rename(i, s.label.text()):
            s.label.setText(self.controller.project.frames[i].label)   # refused: put the old label back

    # ---- drag to reorder ---------------------------------------------------------------------
    def _gap_at(self, x: int) -> int:
        """The gap (0..n) nearest to x, in panel coordinates. Gap g is just before frame g."""
        g = self.first + round((x - (FIRST_X - 3)) / PITCH)
        return max(0, min(self.frame_count(), g))

    def _in_strip(self, pos: QPoint) -> bool:
        return QRect(FIRST_X - 20, THUMB_Y - 8, VISIBLE * PITCH + 40, 220 - THUMB_Y).contains(pos)

    def _drag_move(self, slot: int, pos: QPoint) -> None:
        if self.controller.edit.mode:
            return                                   # no reordering while editing
        if self._drag_src is None:
            self._drag_src = self.first + slot
            self.grabKeyboard()
        if self._in_strip(pos):
            self._drag_gap = self._gap_at(pos.x())
            x = FIRST_X - 4 + (self._drag_gap - self.first) * PITCH
            self.marker.move(x, THUMB_Y)
            self.marker.show()
        else:
            self._drag_gap = None
            self.marker.hide()

    def _drag_end(self, slot: int, pos: QPoint) -> None:
        src, gap = self._drag_src, self._drag_gap
        self._cancel_drag()
        if src is None or gap is None or not self._in_strip(pos):
            return                                   # dropped outside the strip: nothing changes
        dst = gap if gap <= src else gap - 1
        if dst != src:
            self.controller.move_frame(src, dst)

    def _cancel_drag(self) -> None:
        if self._drag_src is not None:
            self.releaseKeyboard()
        self._drag_src = self._drag_gap = None
        self.marker.hide()

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key_Escape and self._drag_src is not None:
            self._cancel_drag()                      # Esc cancels a drag
            e.accept()
            return
        super().keyPressEvent(e)
