"""Colour editor panel (FR-3.13): choose a colour with the colour square, the R/G/B sliders or the Hex box,
then click a palette square to overwrite it. Also sets the transparent colour and has the eyedropper."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QFrame, QLabel, QLineEdit, QPushButton, QSlider, QWidget

from src.app.controller import Controller
from src.app.panel import Panel
from src.app.pixel_icons import SIZE, eyedropper
from src.app.theme import TOGGLE_BUTTON_STYLE
from src.core import palette
from src.core.colour import Colour, level_to_8bit, snap_colour, to_hex, to_level, parse_hex

ARMED = "#FFD24D"          # yellow border: this box will be used by the next click on a palette square
NORMAL = "#e6e8ee"


class ColourSquare(QWidget):
    """The 128 x 128 colour square, drawn 1:1, with a ring marking the chosen colour."""
    picked = Signal(int, int, str)            # x, y, "primary" (left button) or "secondary" (right button)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(palette.SQUARE, palette.SQUARE)
        self.system = None
        self._image: QImage | None = None
        self.marker: tuple[int, int, int, int] | None = None
        self.setCursor(Qt.CrossCursor)

    def set_system(self, system) -> None:
        self.system = system
        if system is None:
            self._image = None
        else:
            img = palette.square_image(system)
            self._image = QImage(img.tobytes(), img.width, img.height, img.width * 3, QImage.Format_RGB888).copy()
        self.marker = None
        self.update()

    def set_marker(self, colour: Colour | None, hint: tuple[int, int] | None = None) -> None:
        self.marker = (palette.marker_rect(self.system, colour, hint)
                       if self.system is not None and colour is not None else None)
        self.update()

    def mousePressEvent(self, event) -> None:
        if self.system is not None and event.button() in (Qt.LeftButton, Qt.RightButton):
            self._pick(event.position().toPoint(), event.button())

    def mouseMoveEvent(self, event) -> None:
        if self.system is not None and event.buttons() & (Qt.LeftButton | Qt.RightButton):
            self._pick(event.position().toPoint(), Qt.LeftButton if event.buttons() & Qt.LeftButton else Qt.RightButton)

    def _pick(self, pt: QPoint, button) -> None:
        self.picked.emit(max(0, min(127, pt.x())), max(0, min(127, pt.y())),
                         "primary" if button == Qt.LeftButton else "secondary")

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        if self._image is not None:
            p.drawImage(0, 0, self._image)
        if self.marker is not None:
            x, y, w, h = self.marker
            cx, cy = x + w // 2, y + h // 2
            cx, cy = max(5, min(122, cx)), max(5, min(122, cy))
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor(0, 0, 0), 4))
            p.drawEllipse(QPoint(cx, cy), 4, 4)
            p.setPen(QPen(QColor(255, 255, 255), 2))
            p.drawEllipse(QPoint(cx, cy), 4, 4)


class Swatch(QAbstractButton):
    """A 36 x 36 colour box with a border that turns yellow when armed."""

    def __init__(self, parent: QWidget, text: str = "", clickable: bool = True) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.colour: Colour = (0, 0, 0)
        self.armed = False
        self.text_mark = text
        self.setEnabled(True)
        if not clickable:
            self.setFocusPolicy(Qt.NoFocus)

    def set_colour(self, c: Colour) -> None:
        self.colour = c
        self.update()

    def set_armed(self, armed: bool) -> None:
        self.armed = armed
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(*self.colour))
        w = 2 if self.armed else 1
        p.setPen(QPen(QColor(ARMED if self.armed else NORMAL), w))
        p.drawRect(QRect(0, 0, 35, 35) if w == 1 else QRect(1, 1, 33, 33))
        if self.text_mark:
            p.setPen(QColor(255, 255, 255))
            p.drawText(self.rect(), Qt.AlignCenter, self.text_mark)


class ColourPair(QWidget):
    """Two overlapping 22 x 22 squares in the 36 x 36 space of the old single colour box: the primary colour in front
    (top left) and the secondary colour behind (bottom right). The one being edited has the highlighted border; the
    border turns yellow when it is armed to overwrite a palette square."""
    clicked = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.colours = {"primary": (0, 0, 0), "secondary": (0, 0, 0)}
        self.current = "primary"
        self.armed = False
        self.setFocusPolicy(Qt.NoFocus)

    RECTS = {"secondary": QRect(14, 14, 22, 22), "primary": QRect(0, 0, 22, 22)}

    def set_state(self, primary: Colour, secondary: Colour, current: str, armed: bool) -> None:
        self.colours = {"primary": primary, "secondary": secondary}
        self.current, self.armed = current, armed
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            pt = event.position().toPoint()
            self.clicked.emit("primary" if self.RECTS["primary"].contains(pt) else "secondary")

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        for which in ("secondary", "primary"):                      # primary last: it is in front
            r = self.RECTS[which]
            p.fillRect(r, QColor(*self.colours[which]))
            on = which == self.current
            colour = ARMED if (on and self.armed) else "#ffffff" if on else "#8a8f9c"
            p.setPen(QPen(QColor(colour), 2 if on else 1))
            p.drawRect(r.adjusted(1, 1, -1, -1) if on else r.adjusted(0, 0, -1, -1))
        p.setPen(QPen(QColor(10, 10, 12), 1))


class EyedropperButton(QAbstractButton):
    """A pixel-art eyedropper whose liquid is the preview colour."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.armed = False
        self.colour: Colour = (0, 146, 255)
        self.setToolTip("Colour picker (eyedropper)")

    def set_armed(self, armed: bool) -> None:
        self.armed = armed
        self.update()

    def set_colour(self, colour: Colour) -> None:
        self.colour = colour
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1e1f24"))
        p.setPen(QPen(QColor(ARMED if self.armed else "#4a4e5a"), 2 if self.armed else 1))
        p.drawRect(QRect(1, 1, 33, 33) if self.armed else QRect(0, 0, 35, 35))
        img = QImage(SIZE, SIZE, QImage.Format_ARGB32)
        img.fill(0)
        for (x, y), c in eyedropper(tuple(self.colour)).items():
            img.setPixelColor(x, y, QColor(*c))
        p.drawImage(QRect(0, 0, 36, 36), img)              # no smoothing: pixel art stays crisp


PANEL_H = 204                # the bottom half of the one card (the palette is the top half)
BOTTOM_CARD_STYLE = ("Panel { background: #2a2c33; border: 1px solid #3a3d47; border-top: none; "
                     "border-top-left-radius: 0px; border-top-right-radius: 0px; "
                     "border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; }")


class ColourEditorPanel(Panel):
    def __init__(self, parent: QWidget, controller: Controller) -> None:
        super().__init__("", parent)
        self.title.hide()                                   # the card's title is on the palette half
        self.setStyleSheet(BOTTOM_CARD_STYLE)
        self.divider = QFrame(self)                         # thin line between the palette and the editor
        self.divider.setGeometry(16, 0, 304, 1)
        self.divider.setStyleSheet("background: #3a3d47; border: none;")
        self.controller = controller
        self.colour: Colour = (0, 0, 0)            # the preview colour (always valid for the system)
        self.armed = False                         # the next click on a palette square overwrites it
        self.transparent_armed = False
        self.eyedropper_armed = False
        self._hint: tuple[int, int] | None = None
        self._busy = False

        self.square = ColourSquare(self)
        self.square.move(16, 16)
        self.square.picked.connect(self._square_picked)

        self.sliders: list[QSlider] = []
        self.values: list[QLabel] = []
        self.minus_btns: list[QPushButton] = []
        self.plus_btns: list[QPushButton] = []
        for i, (ch, accent) in enumerate((("R", "#e05a5a"), ("G", "#5ac86e"), ("B", "#5a8ae0"))):
            y = 20 + i * 28
            lab = QLabel(ch, self)
            lab.setGeometry(160, y, 14, 22)
            minus = self._step_button("\u2212", 178, y, -1, i)      # one level down
            s = QSlider(Qt.Horizontal, self)
            s.setGeometry(204, y, 58, 22)
            s.setStyleSheet(f"QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}")
            plus = self._step_button("+", 266, y, 1, i)               # one level up
            val = QLabel("0", self)
            val.setGeometry(292, y, 28, 22)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            s.valueChanged.connect(self._slider_moved)
            self.sliders.append(s)
            self.values.append(val)
            self.minus_btns.append(minus)
            self.plus_btns.append(plus)

        hex_label = QLabel("Hex", self)
        hex_label.setGeometry(160, 106, 28, 24)
        self.hex = QLineEdit(self)
        self.hex.setGeometry(192, 106, 88, 24)
        self.hex.setMaxLength(7)
        self.hex.editingFinished.connect(self._hex_finished)

        self.t_box = Swatch(self, "T")
        self.t_box.move(16, 156)
        self.t_box.setToolTip("Set transparent colour")
        self.t_box.clicked.connect(self._toggle_transparent)
        self.t_label = QLabel("Transparent colour", self)
        self.t_label.setGeometry(62, 156, 130, 36)
        self.t_label.setStyleSheet("font-weight: 600;")
        self.cols = {"primary": (0, 0, 0), "secondary": (0, 0, 0)}   # primary (front) and secondary (behind) colours
        self.current = "primary"                    # which of the two the square, sliders and Hex box are editing
        self.preview = ColourPair(self)
        self.preview.move(238, 156)
        self.preview.setToolTip("Primary colour (front) and secondary colour (behind). Click one to edit it, then "
                                "click a palette square to overwrite that square. Left click on the colour square or "
                                "the picker sets the primary colour, right click the secondary.")
        self.preview.clicked.connect(self._pair_clicked)
        self.eyedropper = EyedropperButton(self)
        self.eyedropper.move(284, 156)
        self.eyedropper.clicked.connect(self._toggle_eyedropper)

        controller.project_changed.connect(self._project_changed)
        controller.frames_changed.connect(self._refresh_transparent)
        controller.palette_clicked.connect(lambda slot: self._palette_clicked(slot, "primary"))
        controller.palette_right_clicked.connect(lambda slot: self._palette_clicked(slot, "secondary"))
        controller.frame_pixel_clicked.connect(lambda c: self._pixel_clicked(c, "primary"))
        controller.frame_pixel_right_clicked.connect(lambda c: self._pixel_clicked(c, "secondary"))

    def _step_button(self, text: str, x: int, y: int, delta: int, channel: int) -> QPushButton:
        b = QPushButton(text, self)
        b.setGeometry(x, y, 22, 22)
        b.setStyleSheet(TOGGLE_BUTTON_STYLE + "QPushButton { padding: 0; font-size: 14px; }")
        b.setFocusPolicy(Qt.NoFocus)
        b.setAutoRepeat(True)
        b.setAccessibleName(("Decrease " if delta < 0 else "Increase ") + "RGB"[channel])
        b.clicked.connect(lambda: self.sliders[channel].setValue(self.sliders[channel].value() + delta))
        return b

    # ---- state ------------------------------------------------------------------------------------
    def _bits(self) -> int:
        p = self.controller.project
        return p.system.bits if p else 3

    def _project_changed(self) -> None:
        p = self.controller.project
        self.square.set_system(p.system if p else None)
        top = (1 << p.system.bits) - 1 if p else 7
        self._busy = True
        for s in self.sliders:
            s.setRange(0, top)
        self._busy = False
        self._disarm()
        self._hint = None
        pal = p.palette() if p else [(0, 0, 0)]
        self.cols = {"primary": pal[0], "secondary": pal[1] if len(pal) > 1 else pal[0]}
        self.current = "primary"
        self._set_colour(pal[0])
        self._refresh_transparent()

    def _refresh_transparent(self) -> None:
        p = self.controller.project
        self.t_box.set_colour(p.transparent if p else (0, 0, 0))

    def _set_colour(self, colour: Colour, arm: bool = False, which: str | None = None) -> None:
        """Set the colour being edited (the primary or the secondary one, snapped) and bring the square marker,
        sliders and Hex box into line."""
        p = self.controller.project
        bits = self._bits()
        if which is not None:
            self.current = which
        self.colour = snap_colour(colour, bits)
        self.cols[self.current] = self.colour
        self._busy = True
        for s, v, lab in zip(self.sliders, self.colour, self.values):
            s.setValue(to_level(v, bits))
            lab.setText(str(to_level(v, bits)))
        self.hex.setText(to_hex(self.colour))
        self._busy = False
        self.controller.edit.editor_colour = self.colour
        self.controller.edit.set_colours(self.cols["primary"], self.cols["secondary"])
        self.eyedropper.set_colour(self.colour)
        self.square.set_marker(self.colour if p else None, self._hint)
        if arm:
            self._arm("preview")
        self._sync_pair()

    def _sync_pair(self) -> None:
        self.preview.set_state(self.cols["primary"], self.cols["secondary"], self.current, self.armed)

    def _arm(self, which: str | None) -> None:
        self.armed = which == "preview"
        self.transparent_armed = which == "transparent"
        self.eyedropper_armed = which == "eyedropper"
        self.controller.eyedropper_armed = self.eyedropper_armed
        self._sync_pair()
        self.t_box.set_armed(self.transparent_armed)
        self.eyedropper.set_armed(self.eyedropper_armed)

    def _disarm(self) -> None:
        self._arm(None)

    # ---- user edits -----------------------------------------------------------------------------------
    def _square_picked(self, x: int, y: int, which: str = "primary") -> None:
        p = self.controller.project
        if p is None:
            return
        self._hint = (x, y)
        self._set_colour(palette.colour_at(p.system, x, y), arm=True, which=which)

    def _slider_moved(self, _value: int) -> None:
        if self._busy or self.controller.project is None:
            return
        bits = self._bits()
        self._hint = None
        self._set_colour(tuple(level_to_8bit(s.value(), bits) for s in self.sliders), arm=True)

    def _hex_finished(self) -> None:
        if self.controller.project is None:
            return
        c = parse_hex(self.hex.text())
        if c is None:
            self.hex.setText(to_hex(self.colour))      # not a colour: back to the current one
            return
        if snap_colour(c, self._bits()) == self.colour:
            self.hex.setText(to_hex(self.colour))          # nothing changed (or snapped to the same colour)
            return
        self._hint = None
        self._set_colour(c, arm=True)

    def _pair_clicked(self, which: str) -> None:
        """A click on the primary or secondary square: the first click chooses it for editing, a click on the one
        already being edited arms it (or disarms it) for overwriting a palette square."""
        if which == self.current:
            self._arm(None if self.armed else "preview")
        else:
            self._disarm()
            self._hint = None
            self._set_colour(self.cols[which], which=which)

    def _toggle_transparent(self) -> None:
        self._arm(None if self.transparent_armed else "transparent")

    def _toggle_eyedropper(self) -> None:
        self._arm(None if self.eyedropper_armed else "eyedropper")

    # ---- clicks elsewhere ---------------------------------------------------------------------------
    def _palette_clicked(self, slot: int, which: str = "primary") -> None:
        p = self.controller.project
        if p is None:
            return
        colours = p.palette()
        if not 0 <= slot < len(colours):
            return                                      # a free slot does nothing
        if self.eyedropper_armed:
            self._hint = None
            self._set_colour(colours[slot], arm=True, which=which)
        elif which != "primary":
            if self.controller.edit.mode and not (self.transparent_armed or self.armed):
                self._hint = None
                self._set_colour(colours[slot], which="secondary")      # right click: the secondary colour
        elif self.transparent_armed:
            self.controller.set_transparent(slot)
            self._disarm()
        elif self.armed:
            old = colours[slot]
            if self.controller.replace_colour(slot, self.colour):
                for k in self.cols:                     # the other colour follows if it was the square replaced
                    if k != self.current and self.cols[k] == old:
                        self.cols[k] = self.colour
                self._disarm()                          # the colours stay, but nothing is armed any more
                self._set_colour(self.colour)
            # (a cancelled merge leaves it armed)
        elif self.controller.edit.mode:
            self._hint = None
            self._set_colour(colours[slot], which="primary")            # Edit mode: left click, the primary colour

    def _pixel_clicked(self, colour, which: str = "primary") -> None:
        if self.eyedropper_armed:
            self._hint = None
            self._set_colour(tuple(colour), arm=True, which=which)
