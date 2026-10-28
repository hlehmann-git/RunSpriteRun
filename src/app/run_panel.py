"""RunSpriteRun window (FR-3.3): shows what RunSpriteRun is doing, with the Scale toggle and Zoom buttons.
The keys and Esc are handled by the main window and the controller; this panel only displays."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QLabel, QPushButton, QWidget

from src.app.controller import Controller
from src.app.panel import Panel
from src.app.theme import TOGGLE_BUTTON_STYLE
from src.app.sprite_view import SpriteView, offer_to_picker


class ToggleSwitch(QAbstractButton):
    """A small on/off switch (the Scale toggle)."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        track = QColor("#4da3ff" if on else "#5b606e")
        if not self.isEnabled():
            track = QColor("#3a3d47")
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, 40, 22), 11, 11)
        p.setBrush(QColor("#0b1220"))
        p.drawEllipse(QRectF(21 if on else 3, 3, 16, 16))


class RunPanel(Panel):

    def __init__(self, parent: QWidget, controller: Controller) -> None:
        super().__init__("RunSpriteRun window", parent)
        self.controller = controller
        self.view = SpriteView(self, grid=False)         # the RunSpriteRun window has no grid at any zoom
        self.view.move(16, 38)
        offer_to_picker(self.view, controller)            # the colour picker can take a colour from here
        self.zoom = 1
        self.max_zoom = 1
        y = 299
        self.scale_label = QLabel("Scale", self)
        self.scale_label.adjustSize()
        self.scale_label.move(16, y + 11 - self.scale_label.height() // 2)
        self.switch = ToggleSwitch(self)
        self.switch.move(self.scale_label.x() + self.scale_label.width() + 6, y)
        self.zoom_label = QLabel("Zoom", self)
        self.zoom_label.adjustSize()
        self.zoom_label.move(self.switch.x() + 40 + 14, y + 11 - self.zoom_label.height() // 2)
        self.minus = QPushButton("−", self)
        self.plus = QPushButton("+", self)
        x = self.zoom_label.x() + self.zoom_label.width() + 6
        for b in (self.minus, self.plus):
            b.setGeometry(x, y, 22, 22)
            b.setStyleSheet(TOGGLE_BUTTON_STYLE + "QPushButton { padding: 0; font-size: 14px; }")
            x += 22 + 4
        self.minus.setAccessibleName("Zoom out")
        self.plus.setAccessibleName("Zoom in")

        self.switch.clicked.connect(self._toggle_scale)
        self.minus.clicked.connect(lambda: self._set_zoom(self.zoom - 1))
        self.plus.clicked.connect(lambda: self._set_zoom(self.zoom + 1))
        controller.project_changed.connect(self._project_changed)
        controller.run_frame.connect(self._show)

    # ---- zoom -----------------------------------------------------------------------------------
    def _project_changed(self) -> None:
        p = self.controller.project
        self.max_zoom = self.view.max_zoom(p.width, p.height) if p else 1
        self.zoom = self.max_zoom                      # a project starts Scaled
        self._apply_zoom()

    def _set_zoom(self, zoom: int) -> None:
        self.zoom = max(1, min(self.max_zoom, zoom))
        self._apply_zoom()

    def _toggle_scale(self) -> None:
        """Scaled = the largest zoom; Actual size = 1x (one source pixel per physical screen pixel)."""
        self.zoom = 1 if self.zoom == self.max_zoom else self.max_zoom
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        self.view.set_zoom(self.zoom)
        self.switch.setChecked(self.zoom == self.max_zoom)
        self.minus.setEnabled(self.zoom > 1)
        self.plus.setEnabled(self.zoom < self.max_zoom)
        self.switch.update()

    # ---- display --------------------------------------------------------------------------------
    def _show(self, index: int) -> None:
        p = self.controller.project
        if p is None or not 0 <= index < len(p.frames):
            self.view.set_sprite(None)
            return
        self.view.set_sprite(p.frames[index].image, p.transparent)
