"""The Edit panel (V2.0), in the old Keys slot (688 x 208): a blue head with the RunSpriteRun | Edit mode toggle,
Layers and Action icons on the left, the Tools grid in the middle and a scrollable Options area on the right."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QLabel, QPushButton, QScrollArea, QWidget)

from src.app import edit_flow
from src.app.controller import Controller
from src.app.edit_session import DEFAULT_OPTIONS, STYLES
from src.app.panel import Panel
from src.core.layers import LAYER_NAMES
from src.core.tools import MAX_THICKNESS

ICONS = Path(__file__).parent / "assets" / "icons"
BOX, LINE, SEL_BG, BLUE, ORANGE = QColor("#1e2025"), QColor("#555964"), QColor("#2e4664"), QColor("#4da3ff"), QColor("#ff9828")
ICON_LIGHT = QColor(215, 220, 230)
TOOL_GRID = ["pencil", "eraser", "bucket", "select", "move", "plus", "line", "square", "circle"]
TOOL_TITLES = {"pencil": "Pencil", "eraser": "Eraser", "bucket": "Bucket", "select": "Select", "move": "Move",
               "plus": "+ Colour", "line": "Line", "square": "Square", "circle": "Circle"}
TOOL_TIPS = {"pencil": "Pencil (P)", "eraser": "Eraser (E) - paints the transparent colour", "bucket": "Bucket (B) - fill",
             "select": "Select (S) - drag a rectangle", "move": "Move (M)", "plus": "+ colour: add the Colour editor's colour to the palette",
             "line": "Line (L)", "square": "Square (R)", "circle": "Circle (O)"}
ACTION_TIPS = {"mirror_v": "Mirror vertically: click here, then click in the Frame view to place the line. What you draw on one side appears on the other. Click again to switch off.",
               "mirror_h": "Mirror horizontally: click here, then click in the Frame view to place the line. What you draw above appears below. Click again to switch off.",
               "rotate_right": "Rotate 90 degrees right", "rotate_left": "Rotate 90 degrees left", "rotate_180": "Rotate 180 degrees",
               "flip_h": "Flip horizontally (left to right)", "flip_v": "Flip vertically (top to bottom)",
               "undo": "Undo (Ctrl+Z)", "redo": "Redo (Ctrl+Y)"}
PNG_TOOLS = {"pencil", "eraser", "bucket", "select", "move", "square", "circle", "mirror_v", "mirror_h", "rot_right",
             "rot_left", "rot_180", "flip_h", "flip_v"}
HEAD_STYLE = ("QWidget#head { background: #3780cd; border-top-left-radius: 7px; border-top-right-radius: 7px;"
              " border-top: 1px solid #2662a8; border-bottom: 1px solid #78b9ff; }")
SEG_STYLE = ("QPushButton { background: #2662a8; color: #cde1fa; border: none; font-size: 11px; }"
             "QPushButton:checked { background: #ecf0f8; color: #14284a; font-weight: bold; }"
             "QPushButton:disabled { color: #8fa9c9; }")
SMALL_BTN = ("QPushButton { background: #1e2025; border: 1px solid #555964; border-radius: 3px; font-weight: bold; }"
             "QPushButton:hover { background: #2a2d35; } QPushButton:disabled { color: #70737c; }")
SEG2_STYLE = ("QPushButton { background: #1e2025; border: 1px solid #555964; border-radius: 4px; padding: 0 8px; }"
              "QPushButton:checked { background: #3780cd; border: 1px solid #78b9ff; color: white; font-weight: bold; }"
              "QPushButton:disabled { color: #70737c; }")


def _pix(name: str) -> QPixmap:
    f = ICONS / f"{name}_22.png"
    return QPixmap(str(f if f.exists() else ICONS / f"{name}_28.png"))


class Box(QWidget):
    """A thin outlined group with its heading sitting on the top border (Layers, Tools, Action)."""

    def __init__(self, title: str, parent: QWidget, x: int, y: int, w: int, h: int) -> None:
        super().__init__(parent)
        self.title = title
        self.setGeometry(x, y, w, h)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#4a4e5a"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 6.5, self.width() - 1, self.height() - 7), 4, 4)
        f = QFont(self.font())
        f.setPixelSize(10)
        f.setBold(True)
        p.setFont(f)
        w = p.fontMetrics().horizontalAdvance(self.title) + 8
        p.fillRect(QRectF(9, 0, w, 14), QColor("#2a2c33"))
        p.setPen(QColor("#969ba5"))
        p.drawText(QRectF(13, 0, w, 14), Qt.AlignLeft | Qt.AlignVCenter, self.title)


class IconButton(QPushButton):
    """A 32 x 32 square button with a small drawing: a tool, a layer box or an action."""

    def __init__(self, kind: str, parent: QWidget, size: int = 32, checkable: bool = False) -> None:
        super().__init__("", parent)
        self.kind = kind
        self.setFixedSize(size, size)
        self.setCheckable(checkable)
        self.setFocusPolicy(Qt.NoFocus)
        self.pix = _pix(kind) if kind in PNG_TOOLS else _pix("plus_clr") if kind == "plus" else None
        self.selected = False          # drawn like a chosen tool (only used by the tools)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.selected
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(QPen(BLUE if on else QColor("#6a6e7a") if self.underMouse() and self.isEnabled() else LINE, 1))
        p.setBrush(SEL_BG if on else BOX)
        p.drawRoundedRect(r, 3, 3)
        if not self.isEnabled():
            p.setOpacity(0.35)
        w, h = self.width(), self.height()
        k = self.kind
        if k == "eye":
            if self.isChecked():
                p.setPen(QPen(BLUE, 1.3))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QRectF(w / 2 - 7, h / 2 - 3.5, 14, 7))
                p.setPen(Qt.NoPen)
                p.setBrush(BLUE)
                p.drawEllipse(QRectF(w / 2 - 2, h / 2 - 2, 4, 4))
        elif k == "target":
            if self.isChecked():
                p.setPen(QPen(ORANGE, 2))
                p.drawLine(QPointF(w / 2 - 6, h / 2 - 6), QPointF(w / 2 + 6, h / 2 + 6))
                p.drawLine(QPointF(w / 2 + 6, h / 2 - 6), QPointF(w / 2 - 6, h / 2 + 6))
        elif k == "line":
            p.setPen(QPen(ICON_LIGHT, 2.2))
            p.drawLine(QPointF(7, h - 8), QPointF(w - 7, 8))
            p.setPen(Qt.NoPen)
            p.setBrush(BLUE)
            for x, y in ((7, h - 8), (w - 7, 8)):
                p.drawRect(QRectF(x - 2, y - 2, 4, 4))
        elif k in ("undo", "redo"):
            self._arrow(p, w / 2, h / 2, k == "undo")
        elif self.pix is not None:
            p.drawPixmap((w - self.pix.width()) // 2, (h - self.pix.height()) // 2, self.pix)

    @staticmethod
    def _arrow(p: QPainter, cx: float, cy: float, flip: bool) -> None:
        import math
        rad = 7.5
        a0, a1 = (210, -20) if flip else (-30, 200)
        pts = [QPointF(cx + rad * math.cos(math.radians(a0 + (a1 - a0) * i / 20)),
                       cy + rad * math.sin(math.radians(a0 + (a1 - a0) * i / 20))) for i in range(21)]
        p.setPen(QPen(ICON_LIGHT, 2))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath(pts[0])
        for q in pts[1:]:
            path.lineTo(q)
        p.drawPath(path)
        ex, ey, px, py = pts[-1].x(), pts[-1].y(), pts[-3].x(), pts[-3].y()
        dx, dy = ex - px, ey - py
        ln = math.hypot(dx, dy) or 1
        dx, dy = dx / ln, dy / ln
        p.setPen(Qt.NoPen)
        p.setBrush(ICON_LIGHT)
        p.drawPolygon(QPolygonF([QPointF(ex + dx * 4.5, ey + dy * 4.5), QPointF(ex - dy * 3.6, ey + dx * 3.6),
                                 QPointF(ex + dy * 3.6, ey - dx * 3.6)]))


class EditPanel(Panel):
    def __init__(self, parent: QWidget, controller: Controller) -> None:
        super().__init__("", parent)
        self.title.hide()
        self.controller = controller
        self.edit = controller.edit
        body = self.body = QWidget(self)
        body.setGeometry(1, 1, 686, 206)
        # ---- head
        head = QWidget(body)
        head.setObjectName("head")
        head.setGeometry(0, 0, 686, 30)
        head.setStyleSheet(HEAD_STYLE)
        t = QLabel("Edit", head)
        t.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background: transparent;")
        t.move(16, 6)
        self.v1_btn = QPushButton("RunSpriteRun", head)
        self.edit_btn = QPushButton("Edit mode", head)
        for b, x, w in ((self.v1_btn, 77, 96), (self.edit_btn, 173, 82)):
            b.setCheckable(True)
            b.setGeometry(x, 4, w, 22)
            b.setStyleSheet(SEG_STYLE)
            b.setFocusPolicy(Qt.NoFocus)
        self.v1_btn.setToolTip("RunSpriteRun (version 1 behaviour)")
        self.edit_btn.setToolTip("Edit mode: draw on the Frame view")
        self.v1_btn.clicked.connect(self._leave)
        self.edit_btn.clicked.connect(self._enter)
        self.hint = QLabel("", head)
        self.hint.setStyleSheet("color: #ffe9b0; font-size: 11px; background: transparent;")
        self.hint.setGeometry(280, 4, 390, 22)
        self.hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._hint_timer = QTimer(self)
        self._hint_timer.setSingleShot(True)
        self._hint_timer.timeout.connect(lambda: self.hint.setText(""))
        self.edit.notice.connect(self._notice)
        # ---- everything below the head is switched on and off with Edit mode
        self.work = QWidget(body)
        self.work.setGeometry(0, 30, 686, 176)
        self.work.setStyleSheet("QLabel { background: transparent; }")
        Box("LAYERS", self.work, 13, 8, 164, 102)
        Box("TOOLS", self.work, 200, 8, 222, 102)
        Box("ACTION", self.work, 13, 117, 409, 56)
        self.eyes, self.targets = [], []
        for i, name in enumerate(LAYER_NAMES):
            y = 24 + i * 28
            eye = IconButton("eye", self.work, 24, True)
            eye.move(22, y)
            eye.setChecked(True)
            eye.setToolTip(f"Show {name}")
            eye.toggled.connect(lambda on, i=i: self.edit.set_visible(i, on))
            x = IconButton("target", self.work, 24, True)
            x.move(52, y)
            x.setChecked(self.edit.target[i])
            x.setToolTip(f"Edit {name}")
            x.toggled.connect(lambda on, i=i: self.edit.set_target(i, on))
            lab = QLabel(name, self.work)
            lab.setStyleSheet("font-size: 12px; background: transparent;")
            lab.setGeometry(86, y, 90, 24)
            self.eyes.append(eye)
            self.targets.append(x)
        self.actions = {}
        # (button name, how it is drawn): mirror modes first, then rotate and flip, then Undo and Redo
        for i, (name, kind) in enumerate((("mirror_v", "mirror_v"), ("mirror_h", "mirror_h"), ("rotate_right", "rot_right"),
                                          ("rotate_left", "rot_left"), ("rotate_180", "rot_180"), ("flip_h", "flip_h"),
                                          ("flip_v", "flip_v"), ("undo", "undo"), ("redo", "redo"))):
            b = IconButton(kind, self.work)
            b.move(20 + i * 36, 135)
            b.setToolTip(ACTION_TIPS[name])
            self.actions[name] = b
        self.actions["mirror_v"].clicked.connect(lambda: self.edit.toggle_mirror("v"))
        self.actions["mirror_h"].clicked.connect(lambda: self.edit.toggle_mirror("h"))
        for n in ("rotate_right", "rotate_left", "rotate_180", "flip_h", "flip_v"):
            self.actions[n].clicked.connect(lambda _c=False, n=n: self.edit.action(n))
        self.actions["undo"].clicked.connect(self.edit.undo)
        self.actions["redo"].clicked.connect(self.edit.redo)
        controller.selection_changed.connect(lambda _i: self._refresh())
        self.tool_buttons: dict[str, IconButton] = {}
        for i in range(12):
            c, r = i % 6, i // 6
            if i < len(TOOL_GRID):
                name = TOOL_GRID[i]
                b = IconButton(name, self.work)
                b.setToolTip(TOOL_TIPS[name])
                b.clicked.connect(lambda _c=False, n=name: self._tool_clicked(n))
                self.tool_buttons[name] = b
            else:
                b = IconButton("empty", self.work)
                b.setEnabled(False)
            b.move(207 + c * 36, 25 + r * 36)
        self.options_title = self._heading("OPTIONS", 438, 14)
        self.scroll = QScrollArea(self.work)
        self.scroll.setGeometry(432, 22, 238, 146)
        self.scroll.setStyleSheet("QScrollArea { background: #24262c; border: 1px solid #3e414a; border-radius: 4px; }"
                                  "QScrollBar:vertical { background: #1e1f24; width: 10px; border: 1px solid #4a4e5a; border-radius: 4px; margin: 0; }"
                                  "QScrollBar::handle:vertical { background: #aab2c8; border-radius: 3px; min-height: 24px; margin: 1px; }"
                                  "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
                                  "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }")
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.edit.changed.connect(self._refresh)
        controller.frames_changed.connect(self._refresh)
        controller.project_changed.connect(self._refresh)
        self._build_options()
        self._refresh()

    def _heading(self, text: str, x: int, y: int) -> QLabel:
        lab = QLabel(text, self.work)
        lab.setStyleSheet("color: #969ba5; font-size: 10px; font-weight: bold; background: transparent;")
        lab.setGeometry(x, y - 8, 230, 16)
        return lab

    def _enter(self) -> None:
        edit_flow.enter(self.window(), self.edit)
        self._refresh()

    def _leave(self) -> None:
        edit_flow.leave(self.window(), self.edit)
        self._refresh()

    def _notice(self, text: str) -> None:
        self.hint.setText(text)
        self._hint_timer.start(3500)

    def _tool_clicked(self, name: str) -> None:
        if name == "plus":
            self.edit.add_colour()
            return
        self.edit.set_tool(name)

    # ---- state -> widgets ------------------------------------------------------------------------------
    def _refresh(self) -> None:
        e = self.edit
        self.v1_btn.setChecked(not e.mode)
        self.edit_btn.setChecked(e.mode)
        self.work.setEnabled(e.mode)
        for name, b in self.tool_buttons.items():
            b.selected = e.mode and name == e.tool
            b.update()
        plus = self.tool_buttons["plus"]
        p = self.controller.project
        full = p is not None and len(p.palette()) >= p.system.max_colours
        plus.setEnabled(e.mode and not full)
        plus.setToolTip("The palette is full" if full else TOOL_TIPS["plus"])
        can_rotate = e.can_rotate()
        for n in ("rotate_right", "rotate_left"):
            self.actions[n].setEnabled(e.mode and can_rotate)
            self.actions[n].setToolTip(ACTION_TIPS[n] if can_rotate else "Rotating needs a square frame size")
        for n, axis in (("mirror_v", "v"), ("mirror_h", "h")):
            self.actions[n].selected = e.mirror_armed == axis or e.mirror[axis] is not None
            self.actions[n].update()
        self.actions["undo"].setEnabled(e.can_undo)
        self.actions["redo"].setEnabled(e.can_redo)
        if self._built_for != e.tool:
            self._build_options()
        self._refresh_select_buttons()
        for i in range(3):
            for box, val in ((self.eyes[i], e.visible[i]), (self.targets[i], e.target[i])):
                if box.isChecked() != val:
                    box.blockSignals(True)
                    box.setChecked(val)
                    box.blockSignals(False)

    # ---- options for the chosen tool -------------------------------------------------------------------
    _built_for = ""

    def _build_options(self) -> None:
        tool = self.edit.tool
        self._built_for = tool
        self.options_title.setText(f"OPTIONS · {TOOL_TITLES[tool]}")
        page = QWidget()
        page.setStyleSheet("QWidget { background: #24262c; } QLabel { background: transparent; font-size: 12px; }")
        self._y = 8
        o = self.edit.options.get(tool, {})
        if tool in ("pencil", "eraser"):
            if tool == "pencil":
                self._check(page, tool, "pixel_perfect", "Pixel Perfect")
            self._stepper(page, tool, "thickness", "Thickness")
            self._combo(page, tool, "brush", "Brush shape", ["Square", "Round"])
            self._note(page, "Hold Shift: horizontal or vertical line" if tool == "pencil" else "Paints the transparent colour. Hold Shift: horizontal or vertical line")
        elif tool == "bucket":
            self._combo(page, tool, "fill", "Fill", ["Contiguous", "Global"])
            self._combo(page, tool, "source", "Source", ["Visible layers", "Active layer"])
            self._note(page, "Fills the top ticked layer")
        elif tool == "line":
            self._stepper(page, tool, "thickness", "Thickness")
            self._combo(page, tool, "brush", "Brush shape", ["Square", "Round"])
            self._note(page, "Hold Shift: horizontal, vertical or 45°")
        elif tool in ("square", "circle"):
            self._stepper(page, tool, "thickness", "Thickness")
            self._combo(page, tool, "style", "Style", list(STYLES))
            self._check(page, tool, "centre", "Draw from centre")
            self._note(page, "Outline + Fill: outline in the primary colour, fill in the secondary. Hold Shift: "
                       + ("perfect square. " if tool == "square" else "true circle, not an oval. ")
                       + "Thickness 1 is pixel perfect.")
        elif tool == "move":
            self._note(page, "No options")
            self._note(page, "No selection: moves the whole layer. The ticked layers move together; what leaves the frame is cut off when you let go.")
        elif tool == "select":
            self._select_buttons(page)
            self._note(page, "Drag a rectangle. Drag inside it to move the outline; the Move tool moves the pixels. "
                             "Enter fixes a pasted piece, Esc discards it.")
        page.setFixedSize(218, max(self._y + 6, 144))
        self.scroll.setWidget(page)

    def _select_buttons(self, page: QWidget) -> None:
        """Select All, Deselect, Cut, Copy, Paste, Delete (the usual keys work too)."""
        self.select_btns = {}
        items = (("select_all", "Select All", "Ctrl+A", self.edit.select_all), ("deselect", "Deselect", "Esc", self.edit.deselect),
                 ("cut", "Cut", "Ctrl+X", self.edit.cut), ("copy", "Copy", "Ctrl+C", self.edit.copy),
                 ("paste", "Paste", "Ctrl+V", self.edit.paste), ("delete", "Delete", "Delete", self.edit.delete))
        for i, (key, text, keys, fn) in enumerate(items):
            b = QPushButton(text, page)
            b.setGeometry(10 + (i % 2) * 98, self._y + (i // 2) * 28, 92, 24)
            b.setStyleSheet(SEG2_STYLE)
            b.setFocusPolicy(Qt.NoFocus)
            b.setToolTip(f"{text} ({keys})")
            b.clicked.connect(lambda _c=False, fn=fn: fn())
            self.select_btns[key] = b
        self._y += 3 * 28 + 4
        self._refresh_select_buttons()

    def _refresh_select_buttons(self) -> None:
        btns = getattr(self, "select_btns", None)
        e = self.edit
        if not btns or self.edit.tool != "select":
            return
        try:
            has = e.has_selection()
            floating = e.floating is not None
            for key, on in (("select_all", e.mode and not floating), ("deselect", has and not floating),
                            ("cut", e.can_cut), ("copy", e.can_copy), ("paste", e.can_paste),
                            ("delete", e.can_cut)):
                btns[key].setEnabled(on)
        except RuntimeError:
            self.select_btns = {}                      # the buttons were deleted with an old Options page

    def _row_label(self, page: QWidget, text: str, y: int) -> None:
        lab = QLabel(text, page)
        lab.setGeometry(10, y, 100, 22)

    def _check(self, page, tool, key, text) -> None:
        cb = QCheckBox(text, page)
        cb.setGeometry(10, self._y, 190, 22)
        cb.setChecked(bool(self.edit.options[tool][key]))
        cb.toggled.connect(lambda on: self.edit.set_option(tool, key, on))
        self._y += 28

    def _stepper(self, page, tool, key, text) -> None:
        y = self._y
        self._row_label(page, text, y)
        value = QLabel(str(self.edit.options[tool][key]), page)
        value.setAlignment(Qt.AlignCenter)
        value.setGeometry(136, y, 30, 22)
        value.setStyleSheet("background: #1e2025; border: 1px solid #555964; border-radius: 3px;")

        def bump(d: int) -> None:
            v = max(1, min(MAX_THICKNESS, self.edit.options[tool][key] + d))
            value.setText(str(v))
            self.edit.set_option(tool, key, v)
        for txt, x, d in (("-", 112, -1), ("+", 170, 1)):
            b = QPushButton(txt, page)
            b.setGeometry(x, y, 22, 22)
            b.setStyleSheet(SMALL_BTN)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _c=False, d=d: bump(d))
        self._y += 30

    def _combo(self, page, tool, key, text, items) -> None:
        y = self._y
        self._row_label(page, text, y)
        cb = QComboBox(page)
        cb.addItems(items)
        cb.setCurrentText(self.edit.options[tool][key])
        cb.setGeometry(88, y, 118, 22)
        cb.activated.connect(lambda _i: self.edit.set_option(tool, key, cb.currentText()))
        self._y += 30

    def _note(self, page, text) -> None:
        lab = QLabel(text, page)
        lab.setWordWrap(True)
        lab.setStyleSheet("color: #969ba5; font-size: 11px; background: transparent;")
        lab.setFixedWidth(190)
        lab.setFixedHeight(max(16, lab.heightForWidth(190) + 2))
        lab.move(10, self._y)
        self._y += lab.height() + 6
