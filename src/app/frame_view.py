"""Frame view panel (FR-3.3): the selected frame with the pixel grid, and the Frame number and
Frame label drop-downs in the title row."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QWidget

from src.app.theme import short_popup
from src.app.arrow_button import ArrowButton
from src.app.controller import Controller
from src.app.panel import PANEL_STYLE, Panel
from src.app.cursors import cursor_for
from src.app.sprite_view import SpriteView
from src.app.theme import TOGGLE_BUTTON_STYLE


EDIT_BORDER = "FrameViewPanel { background: #2a2c33; border: 2px solid #ff9828; border-radius: 8px; }"


class FrameViewPanel(Panel):
    def __init__(self, parent: QWidget, controller: Controller) -> None:
        super().__init__("Frame view", parent)
        self.controller = controller
        self.number = QComboBox(self)
        self.label = QComboBox(self)
        short_popup(self.number)
        short_popup(self.label)
        self.number.setGeometry(104, 8, 64, 26)
        self.label.setGeometry(174, 8, 100, 26)
        self.view = SpriteView(self, grid=controller.settings.grid)
        self.view.move(16, 38)
        self.view.pixel_clicked.connect(self._pixel_clicked)
        self.view.pixel_right_clicked.connect(self._pixel_right_clicked)
        self.view.drag_started.connect(self._drag_started)
        self.view.placed.connect(controller.edit.place_mirror)
        self.view.drag_moved.connect(lambda x, y, s: self.controller.edit.move((x, y), s))
        self.view.drag_ended.connect(lambda x, y, s: self.controller.edit.release((x, y), s))
        controller.edit.changed.connect(self._edit_changed)
        controller.edit.frame_edited.connect(self._frame_edited)
        # step through ALL frames in timeline order (not limited to a group); greyed out at the first / last frame
        self.prev_btn = ArrowButton("left", self, "Previous frame")
        self.next_btn = ArrowButton("right", self, "Next frame")
        self.prev_btn.move(134, 299)
        self.next_btn.move(164, 299)
        self.prev_btn.clicked.connect(lambda: self.controller.select(self.controller.selected - 1))
        self.next_btn.clicked.connect(lambda: self.controller.select(self.controller.selected + 1))
        self.edit_note = QLabel("", self)                 # Edit mode: which frame can be drawn on
        self.edit_note.setGeometry(16, 297, 112, 26)
        self.edit_note.hide()
        # zoom (Edit mode only): the wheel does the same; Space + drag or the middle button pans
        tip = "Mouse wheel zooms. Hold Space and drag, or drag with the middle button, to move the picture."
        self.zoom_label = QLabel("", self)
        self.zoom_label.setStyleSheet("font-size: 12px; background: transparent;")
        self.zoom_label.setToolTip(tip)
        self.zoom_out = QPushButton("−", self)
        self.zoom_in = QPushButton("+", self)
        for b, name in ((self.zoom_out, "Zoom out"), (self.zoom_in, "Zoom in")):
            b.setFixedSize(22, 22)
            b.setStyleSheet(TOGGLE_BUTTON_STYLE + "QPushButton { padding: 0; font-size: 14px; }")
            b.setFocusPolicy(Qt.NoFocus)
            b.setAccessibleName(name)
            b.setToolTip(tip)
            b.hide()
        self.zoom_label.hide()
        self.zoom_out.clicked.connect(lambda: self.view.set_scale(self.view.current_scale() - 1))
        self.zoom_in.clicked.connect(lambda: self.view.set_scale(self.view.current_scale() + 1))
        self.view.zoom_changed.connect(self._zoom_changed)
        self.number.activated.connect(self.controller.select)
        self.label.activated.connect(self.controller.select)
        controller.project_changed.connect(self._reload)
        controller.frames_changed.connect(self._reload)
        controller.selection_changed.connect(self._show)
        controller.settings_changed.connect(self._grid_setting)

    def set_large(self, large: bool) -> None:
        """Edit mode: a 512 px picture instead of 256 px (the arrows and the note move down)."""
        size = 512 if large else 256
        self.view.setFixedSize(size, size)
        y = 38 + size + 5
        self.prev_btn.move(134, y)
        self.next_btn.move(164, y)
        self.edit_note.setGeometry(16, y - 2, 112, 26)
        self.zoom_label.setGeometry(300, y - 1, 100, 24)
        self.zoom_out.move(408, y)
        self.zoom_in.move(436, y)
        self.view.update()

    def _zoom_changed(self) -> None:
        v = self.view
        n = v.current_scale()
        self.zoom_label.setText(f"Zoom {n}x" + ("  (fit)" if n == v.fit() else ""))
        self.zoom_out.setEnabled(n > v.fit())
        self.zoom_in.setEnabled(n < 64)

    def _grid_setting(self) -> None:
        self.view.grid = self.controller.settings.grid
        self.view.update()

    def _reload(self) -> None:
        p = self.controller.project
        for box in (self.number, self.label):
            box.blockSignals(True)
            box.clear()
        if p is not None:
            self.number.addItems([str(i + 1) for i in range(len(p.frames))])
            self.label.addItems([f.label for f in p.frames])
        for box in (self.number, self.label):
            box.blockSignals(False)
        self._show(self.controller.selected)

    def _update_arrows(self, index: int) -> None:
        p = self.controller.project
        n = len(p.frames) if p is not None else 0
        self.prev_btn.setEnabled(n > 0 and index > 0)
        self.next_btn.setEnabled(n > 0 and index < n - 1)

    def _show(self, index: int) -> None:
        p = self.controller.project
        self._update_arrows(index)
        self._edit_changed()
        if p is None or not p.frames:
            self.view.set_sprite(None)
            return
        for box in (self.number, self.label):
            box.blockSignals(True)
            box.setCurrentIndex(index)
            box.blockSignals(False)
        self.view.set_sprite(self.controller.edit.display_image(index), p.transparent)
        self._zoom_changed()

    def _pixel_clicked(self, x: int, y: int) -> None:
        """Clicking a pixel offers its colour to the eyedropper (FR-3.13)."""
        p = self.controller.project
        if p is not None and p.frames:
            self.controller.frame_pixel_clicked.emit(p.frames[self.controller.selected].image.getpixel((x, y)))

    # ---- Edit mode ------------------------------------------------------------------------------------
    def _edit_changed(self) -> None:
        e = self.controller.edit
        editing = e.mode and self.controller.selected == e.idx
        self.view.draggable = editing or (e.mode and e.tool == "select")     # Select also works on frames only being looked at
        self.view.set_selection(e.selection if e.mode and e.selection is not None and e.sel_idx == self.controller.selected else None)
        self.view.navigable = e.mode
        for w in (self.zoom_label, self.zoom_out, self.zoom_in):
            w.setVisible(e.mode)
        if not e.mode and self.view.scale is not None:
            self.view.reset_zoom()                         # leaving Edit mode puts the zoom back to fit
        self._zoom_changed()
        self.view.set_tool_cursor(cursor_for(e.tool) if editing else None)
        self.view.set_placing(bool(editing and e.mirror_armed))
        self.view.set_guides(e.mirror if e.mode else {})
        self.edit_note.setVisible(e.mode)
        if e.mode:
            if e.floating is not None:
                self.edit_note.setText("PASTING")
                self.edit_note.setStyleSheet("color: #4da3ff; font-weight: bold; font-size: 12px;")
            else:
                self.edit_note.setText("EDITING" if editing else "VIEW ONLY")
                self.edit_note.setStyleSheet("color: #ffb347; font-weight: bold; font-size: 12px;" if editing
                                             else "color: #9aa0ae; font-weight: bold; font-size: 12px;")
        self.setStyleSheet(EDIT_BORDER if e.mode else PANEL_STYLE.replace("Panel {", "FrameViewPanel {", 1))

    def _frame_edited(self, index: int) -> None:
        p = self.controller.project
        if p is not None and index == self.controller.selected and index < len(p.frames):
            self.view.set_sprite(self.controller.edit.display_image(index), p.transparent)

    def _drag_started(self, x: int, y: int, shift: bool) -> None:
        if self.controller.eyedropper_armed:               # the eyedropper takes a colour; it does not draw
            return
        if not self.controller.edit.press((x, y), shift):
            self.view._dragging = False

    def _pixel_right_clicked(self, x: int, y: int) -> None:
        """Right click offers the pixel's colour to the eyedropper as the secondary colour."""
        p = self.controller.project
        if p is not None and p.frames:
            self.controller.frame_pixel_right_clicked.emit(p.frames[self.controller.selected].image.getpixel((x, y)))
