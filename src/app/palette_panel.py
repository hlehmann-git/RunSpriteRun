"""Palette panel (FR-3.13), display only for now: all N slots, used slots show their colour,
free slots are white-outlined blocks with their slot number."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QLabel, QMenu, QWidget

from src.app.controller import Controller
from src.app.panel import Panel

SWATCH, GAP, COLUMNS = 18, 1, 16      # 16 squares per row: 16 slots = 1 row, 32 = 2 rows, 64 = 4 rows
LEFT, TOP, BOTTOM = 16, 40, 14
TITLE = "Palette & Colour editor"        # one card: the palette on top, the colour editor under it


class PaletteGrid(QWidget):
    slot_clicked = Signal(int)
    slot_right_clicked = Signal(int)
    slot_menu = Signal(int, QPoint)        # right click: the square and where to open the menu

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.colours: list[tuple[int, int, int]] = []
        self.slots = 16
        self.transparent: tuple[int, int, int] | None = None
        self.active: tuple[int, int, int] | None = None      # Edit mode: the primary colour
        self.secondary: tuple[int, int, int] | None = None   # Edit mode: the secondary colour
        self.add_slot: int | None = None                      # "add new colour" mode: the free square the colour will go into
        self._resize()

    def rows(self) -> int:
        return max(1, -(-self.slots // COLUMNS))

    def _resize(self) -> None:
        r = self.rows()
        self.setFixedSize(COLUMNS * SWATCH + (COLUMNS - 1) * GAP, r * SWATCH + (r - 1) * GAP)

    def set_state(self, colours, slots, transparent) -> None:
        self.colours, self.slots, self.transparent = colours, slots, transparent
        self._resize()
        self.update()

    def slot_rect(self, i: int) -> QRect:
        return QRect((i % COLUMNS) * (SWATCH + GAP), (i // COLUMNS) * (SWATCH + GAP), SWATCH, SWATCH)

    def slot_at(self, pos) -> int | None:
        for i in range(self.slots):
            if self.slot_rect(i).contains(pos):
                return i
        return None

    def mousePressEvent(self, event) -> None:
        if event.button() in (Qt.LeftButton, Qt.RightButton):
            i = self.slot_at(event.position().toPoint())
            if i is not None and i < len(self.colours):      # free slots do nothing
                if event.button() == Qt.LeftButton:
                    self.slot_clicked.emit(i)
                else:
                    self.slot_menu.emit(i, event.globalPosition().toPoint())

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        small = QFont(self.font())
        small.setPointSizeF(max(5.5, small.pointSizeF() - 2.5))
        for i in range(self.slots):
            r = self.slot_rect(i)
            if i < len(self.colours):
                c = self.colours[i]
                p.fillRect(r, QColor(*c))
                p.setPen(QPen(QColor(10, 10, 12), 1))
                p.drawRect(r.adjusted(0, 0, -1, -1))
                if self.active is not None and c == self.active:
                    p.setPen(QPen(QColor(255, 255, 255), 2))
                    p.drawRect(r.adjusted(1, 1, -2, -2))
                    p.setPen(QPen(QColor(10, 10, 12), 1))
                    p.drawRect(r.adjusted(3, 3, -4, -4))
                elif self.secondary is not None and c == self.secondary:
                    p.setPen(QPen(QColor(255, 255, 255), 1, Qt.DotLine))
                    p.drawRect(r.adjusted(2, 2, -3, -3))
                if c == self.transparent:
                    p.setPen(QColor(255, 255, 255))
                    f = QFont(self.font())
                    f.setBold(True)
                    p.setFont(f)
                    p.drawText(r, Qt.AlignCenter, "T")
            else:
                p.setPen(QPen(QColor(255, 255, 255), 1))      # free slot: white outline and its number
                p.drawRect(r.adjusted(0, 0, -1, -1))
                p.setFont(small)
                p.drawText(r, Qt.AlignCenter, str(i + 1))
            if self.add_slot == i:
                p.setPen(QPen(QColor("#ffd24d"), 2))
                p.setBrush(Qt.NoBrush)
                p.drawRect(r.adjusted(1, 1, -2, -2))


TOP_CARD_STYLE = ("Panel { background: #2a2c33; border: 1px solid #3a3d47; border-bottom: none; "
                  "border-top-left-radius: 8px; border-top-right-radius: 8px; "
                  "border-bottom-left-radius: 0px; border-bottom-right-radius: 0px; }")


class PalettePanel(Panel):
    height_changed = Signal(int)          # the card is taller for more palette slots (16 / 32 / 64)

    def __init__(self, parent: QWidget, controller: Controller) -> None:
        super().__init__(TITLE, parent)
        self.setStyleSheet(TOP_CARD_STYLE)         # top half of the one card; the colour editor is the bottom half
        self.controller = controller
        self.count = QLabel("", self)
        self.count.setStyleSheet("color: #9aa0ae;")
        self.grid = PaletteGrid(self)
        self.grid.move(LEFT, TOP)
        self.grid.slot_clicked.connect(controller.palette_clicked.emit)
        self.grid.slot_menu.connect(self._open_menu)
        controller.project_changed.connect(self.refresh)
        controller.frames_changed.connect(self.refresh)
        controller.edit.changed.connect(self._show_active)
        controller.add_mode_changed.connect(self._add_mode_changed)

    def _open_menu(self, slot: int, where: QPoint) -> None:
        """Right click on a palette square: Set as secondary colour (Edit mode only) and Delete colour."""
        c = self.controller
        p = c.project
        if p is None or c.add_mode or not 0 <= slot < len(p.palette()):
            return
        menu = QMenu(self)
        if c.edit.mode:
            menu.addAction("Set as secondary colour").triggered.connect(lambda: c.palette_right_clicked.emit(slot))
        reason = c.delete_colour_blocked(slot)
        act = menu.addAction("Delete colour")
        act.setEnabled(reason is None)
        if reason is not None:
            act.setToolTip(reason)
        act.triggered.connect(lambda: c.delete_colour(slot))
        menu.exec(where)

    def _add_mode_changed(self, on: bool) -> None:
        p = self.controller.project
        self.grid.add_slot = len(p.palette()) if on and p is not None else None
        self.grid.update()

    def _show_active(self) -> None:
        e = self.controller.edit
        p = self.controller.project
        on = e.mode and p is not None and bool(p.frames)
        self.grid.active = e.draw_colour() if on else None
        self.grid.secondary = e.secondary_colour() if on else None
        self.grid.update()

    def wanted_height(self) -> int:
        return TOP + self.grid.height() + BOTTOM

    def refresh(self) -> None:
        p = self.controller.project
        if p is None:
            self.count.setText("")
            self.grid.set_state([], 16, None)
            self.height_changed.emit(self.wanted_height())
            return
        colours = p.palette()
        slots = p.system.max_colours
        used = len(colours)
        self.count.setText(f"{used} used, {slots - used} free of {slots}")
        self.count.adjustSize()
        self.count.move(self.width() - self.count.width() - 16, 12)
        self.grid.set_state(colours, slots, p.transparent)
        self._show_active()
        self.height_changed.emit(self.wanted_height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.count.move(self.width() - self.count.width() - 16, 12)
