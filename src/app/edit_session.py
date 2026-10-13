"""The editor's state and the drawing engine (V2.0): Edit mode on or off, the chosen tool and its options, which layers
are visible and which are being edited, and the colour being drawn with. A stroke is one Undo step."""
from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QObject, Signal

from src.core import edit as edit_rules, editing, history, layers as L, tools
from src.core.colour import Colour
from src.core.project import Frame

DEFAULT_OPTIONS: dict[str, dict] = {
    "pencil": {"pixel_perfect": True, "thickness": 1, "brush": "Square"},
    "eraser": {"pixel_perfect": False, "thickness": 1, "brush": "Square"},
    "bucket": {"fill": "Contiguous", "source": "Visible layers"},
    "line": {"thickness": 1, "brush": "Square"},
    "square": {"thickness": 1, "style": "Outline", "centre": False},
    "circle": {"thickness": 1, "style": "Outline", "centre": False},
}
STYLES = ("Outline", "Filled", "Outline + Fill")      # Outline + Fill: outline in the primary colour, fill in the secondary
DRAWING_TOOLS = ("pencil", "eraser", "bucket", "line", "square", "circle", "move")
MSG_NO_LAYER = "Tick a visible layer (the X box) to edit it."
MSG_FULL = "The palette is full."
MSG_FLOATING = "A paste is floating: press Enter to fix it in place or Esc to discard it."
MSG_NO_SELECTION = "Select an area first."
MSG_NOTHING_COPIED = "Nothing has been copied yet."
MSG_VIEW_ONLY = "Only the frame being edited can be changed. Go back to it first."


class EditSession(QObject):
    changed = Signal()               # mode, tool, options, layer boxes or the drawing colour changed
    frame_edited = Signal(int)       # the picture of a frame changed (also while a stroke is still being drawn)
    notice = Signal(str)             # a short message for the information bar

    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self.mode = False
        self.tool = "pencil"
        self.options = {k: dict(v) for k, v in DEFAULT_OPTIONS.items()}
        self.visible = [True, True, True]          # ForeGround, Core, BackGround
        self.target = [False, True, False]         # layers an edit changes (Core to start with)
        self.active: Colour | None = None          # the primary colour
        self.secondary: Colour | None = None       # the secondary colour (the fill of Outline + Fill shapes)
        self.idx = -1                              # the frame being edited
        self.new_frame = False
        self.start = None                          # the project as it was when Edit mode began
        self.start_selected = 0
        self.start_dirty = False
        self._undo: list = []
        self._redo: list = []
        self.editor_colour: Colour | None = None   # the Colour editor's colour, for the + colour tool
        self._stroke = None
        self.selection: tuple | None = None        # the selected rectangle (x0, y0, x1, y1), x1 and y1 not included
        self.sel_idx = -1                          # the frame it belongs to
        self.floating: dict | None = None          # a pasted piece that is not fixed in place yet
        self.clipboard: dict | None = None         # what Copy and Cut took: {"w", "h", "layers": {layer: image}}
        controller.selection_changed.connect(self.frame_selected)
        self.mirror: dict[str, int | None] = {"v": None, "h": None}   # guide lines, in half pixels from the frame's left / top
        self.mirror_armed: str | None = None       # "v" or "h": the next left click in the Frame view places that line

    # ---- state ---------------------------------------------------------------------------------------
    # ---- starting and leaving Edit mode ----------------------------------------------------------------
    def begin(self, new: bool = False, where: str = "after", copy: bool = False) -> bool:
        """Start editing the selected frame, or a new frame next to it (where: before, after or first).
        Everything is done on the frame inside the project, but nothing counts until finish(True): finish(False)
        puts the whole project back as it was. Raises EditError if a new frame cannot be made."""
        c = self.controller
        p = c.project
        if p is None or not p.frames or self.mode:
            return False
        sel = c.selected
        start, dirty = c.checkpoint(), p.dirty
        c.stop_run()
        if new:
            src = p.frames[sel]
            frame = Frame(edit_rules.new_frame_label(p), src.image if copy else L.blank(src.image.size, p.transparent),
                          layers=src.layers if copy else None)
            idx = {"before": sel, "after": sel + 1, "first": 0}[where]
            member = edit_rules.group_of_frame(p)[sel]               # the new frame joins the selected frame's group
            if where == "first" and sel != 0:
                member = None                                        # Frame 1 stays outside groups unless it is selected
            edit_rules.insert_frame(p, idx, frame, join=member, anchor=sel, after=where == "after")
        else:
            idx = sel
        self.idx, self.new_frame, self.start, self.start_selected, self.start_dirty = idx, new, start, sel, dirty
        self._undo, self._redo = [], []
        self.mode = True
        c.selected = idx
        self.changed.emit()
        c.frames_changed.emit()
        c.selection_changed.emit(idx)
        return True

    def reset(self) -> None:
        """A different project was opened: forget the editing state."""
        self.mode, self.idx, self.start, self.new_frame, self._stroke = False, -1, None, False, None
        self._undo, self._redo = [], []
        self.selection, self.floating, self.clipboard, self.sel_idx = None, None, None, -1
        self.clear_mirror()
        self.changed.emit()

    def has_changes(self) -> bool:
        p = self.controller.project
        return self.mode and (self.new_frame or self.floating is not None or not self.start.same_as(history.take(p)))

    def finish(self, apply: bool) -> None:
        """Leave Edit mode. apply=True makes the edits final as one Undo step; apply=False drops them (and a new
        frame) and returns everything to how it was."""
        if not self.mode:
            return
        c = self.controller
        p = c.project
        self.cancel()
        self.fix()                                  # a floating paste is fixed in place first
        self.selection, self.sel_idx = None, -1
        start, dirty, sel = self.start, self.start_dirty, self.start_selected
        self.mode = False
        if apply:
            c.commit(start)
            if not start.same_as(history.take(p)):
                p.dirty = True
            else:
                p.dirty = dirty
            c.selected = max(0, min(self.idx, len(p.frames) - 1))
        else:
            history.restore(p, start)
            p.dirty = dirty
            c.selected = max(0, min(sel, len(p.frames) - 1))
        self.idx, self.start, self.new_frame = -1, None, False
        self._undo, self._redo = [], []
        self.clear_mirror()
        self.changed.emit()
        c.frames_changed.emit()
        c.selection_changed.emit(c.selected)

    # ---- mirror drawing: a vertical and/or a horizontal guide line --------------------------------------------
    def clear_mirror(self) -> None:
        self.mirror = {"v": None, "h": None}
        self.mirror_armed = None

    def toggle_mirror(self, axis: str) -> None:
        """The mirror icon: arm it (the next click in the Frame view places the line); with the line already placed
        or the icon already armed, the icon switches that mirror off."""
        if not self.mode:
            return
        if self.mirror_armed == axis:
            self.mirror_armed = None
        elif self.mirror[axis] is not None:
            self.mirror[axis] = None
            self.mirror_armed = None
        else:
            self.mirror_armed = axis
        self.changed.emit()

    def place_mirror(self, fx: float, fy: float) -> bool:
        """Put the armed line on the pixel edge nearest the clicked point (sprite pixel units); it never runs through a pixel."""
        a, p = self.mirror_armed, self.controller.project
        if not (self.mode and a and p is not None):
            return False
        v, size = (fx, p.width) if a == "v" else (fy, p.height)
        self.mirror[a] = 2 * max(0, min(size, round(v)))      # whole pixels only (kept in half pixels)
        self.mirror_armed = None
        self.changed.emit()
        return True

    def mirrored(self, points) -> set:
        """`points` plus their reflections across the placed guide lines (pixels outside the frame are dropped later)."""
        pts = set(points)
        cx, cy = self.mirror["v"], self.mirror["h"]
        if cx is not None:
            pts |= {(cx - x - 1, y) for x, y in pts}
        if cy is not None:
            pts |= {(x, cy - y - 1) for x, y in pts}
        return pts

    # ---- Undo and Redo while editing ---------------------------------------------------------------------
    @property
    def can_undo(self) -> bool:
        return self.mode and (self.floating is not None or bool(self._undo)) and self.controller.selected == self.idx

    @property
    def can_redo(self) -> bool:
        return self.mode and self.floating is None and bool(self._redo) and self.controller.selected == self.idx

    def undo(self) -> bool:
        return self._step(self._undo, self._redo)

    def redo(self) -> bool:
        return self._step(self._redo, self._undo)

    def _step(self, take, give) -> bool:
        if self.mode and self.floating is not None and take is self._undo:
            self.escape()                                  # Undo while a paste floats = discard the paste
            return True
        if not (self.mode and take) or self.controller.selected != self.idx or self.floating is not None:
            return False
        f = self.controller.project.frames[self.idx]
        give.append((f.image, f.layers))
        f.image, f.layers = take.pop()
        self._edited()
        return True

    def _push_undo(self, image, layers) -> None:
        self._undo.append((image, layers))
        del self._undo[:-history.LIMIT]
        self._redo.clear()

    def _edited(self) -> None:
        c = self.controller
        self.changed.emit()
        c.frames_changed.emit()
        c.selection_changed.emit(c.selected)

    def set_tool(self, tool: str) -> None:
        if tool in tools.TOOLS and tool != self.tool:
            self.tool = tool
            self.changed.emit()

    def set_option(self, tool: str, name: str, value) -> None:
        self.options[tool][name] = value
        self.changed.emit()

    def set_visible(self, layer: int, on: bool) -> None:
        self.visible[layer] = on
        self.changed.emit()
        self.controller.selection_changed.emit(self.controller.selected)

    def set_target(self, layer: int, on: bool) -> None:
        self.target[layer] = on
        self.changed.emit()

    def editable(self) -> list[int]:
        """Layers an edit changes: ticked as a target and visible (a hidden layer cannot be drawn on)."""
        return [i for i in range(3) if self.visible[i] and self.target[i]]

    def set_active(self, colour: Colour | None) -> None:
        self.active = tuple(colour) if colour is not None else None
        self.changed.emit()

    def set_colours(self, primary: Colour, secondary: Colour) -> None:
        self.active, self.secondary = tuple(primary), tuple(secondary)
        self.changed.emit()

    def draw_colour(self) -> Colour:
        p = self.controller.project
        pal = p.palette()
        if self.active in pal:
            return self.active
        for c in pal:
            if c != p.transparent:
                return c
        return pal[0]

    def secondary_colour(self) -> Colour:
        p = self.controller.project
        return self.secondary if self.secondary in p.palette() else self.draw_colour()

    def display_image(self, index: int):
        """What the Frame view shows: in Edit mode only the visible layers."""
        p = self.controller.project
        f = p.frames[index]
        if not self.mode or index != self.idx or all(self.visible):
            return f.image
        return L.flatten(L.layers_of(f, p.transparent), p.transparent, self.visible)

    # ---- the + colour tool ---------------------------------------------------------------------------
    def can_add_colour(self) -> bool:
        p = self.controller.project
        return p is not None and self.editor_colour is not None and editing.can_add_colour(p, self.editor_colour)

    def add_colour(self) -> bool:
        p = self.controller.project
        if p is None or self.editor_colour is None:
            return False
        if len(p.palette()) >= p.system.max_colours:
            self.notice.emit(MSG_FULL)
            return False
        before = self.controller.checkpoint()
        if not editing.add_colour(p, self.editor_colour):
            return False                                  # already in the palette
        self.controller.commit(before)                    # (nothing is recorded while Edit mode is on)
        self.controller.frames_changed.emit()
        self.changed.emit()
        return True

    # ---- strokes -------------------------------------------------------------------------------------
    def press(self, pos, shift: bool = False) -> bool:
        c = self.controller
        p = c.project
        if not self.mode or p is None or not p.frames or self.tool == "plus" or self.mirror_armed:
            return False
        pos = tuple(pos)
        viewing = c.selected != self.idx                   # another frame is only being looked at
        if self.floating is not None:                      # a paste floats: only dragging it is allowed
            fl = self.floating
            if self.tool in ("select", "move") and not viewing and self._inside(pos, self._float_rect()):
                self._stroke = {"kind": "float", "start": pos, "x": fl["x"], "y": fl["y"], "idx": self.idx}
                return True
            self.notice.emit(MSG_FLOATING)
            return False
        if self.tool == "select":
            return self._press_select(pos)
        if viewing:
            return False
        targets = self.editable()
        if not targets:
            self.notice.emit(MSG_NO_LAYER)
            return False
        idx = c.selected
        f = p.frames[idx]
        self._stroke = {"idx": idx, "targets": targets, "base": L.layers_of(f, p.transparent), "image": f.image,
                        "layers": f.layers, "start": pos, "path": [pos]}
        if self.tool == "move" and self.selection is not None and self.sel_idx == idx:
            self._stroke["kind"] = "movesel"
            self._stroke["rect"] = self.selection
        self._update(pos, shift)
        return True

    # ---- the Select tool ---------------------------------------------------------------------------------
    @staticmethod
    def _inside(pos, rect) -> bool:
        return rect is not None and rect[0] <= pos[0] < rect[2] and rect[1] <= pos[1] < rect[3]

    def _press_select(self, pos) -> bool:
        idx = self.controller.selected
        if self.selection is not None and self.sel_idx == idx and self._inside(pos, self.selection):
            self._stroke = {"kind": "selmove", "idx": idx, "start": pos, "rect": self.selection}      # moves the outline only
        else:
            self._stroke = {"kind": "selrect", "idx": idx, "start": pos, "moved": False}
        return True

    def _frame_rect(self, a, b) -> tuple | None:
        """The rectangle between two pixels (both included), cut to the frame; None if nothing is left."""
        p = self.controller.project
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(p.width, x1 + 1), min(p.height, y1 + 1)
        return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None

    def _float_rect(self) -> tuple:
        fl = self.floating
        return (fl["x"], fl["y"], fl["x"] + fl["w"], fl["y"] + fl["h"])

    def _cut_to_frame(self, rect) -> tuple | None:
        p = self.controller.project
        x0, y0, x1, y1 = max(0, rect[0]), max(0, rect[1]), min(p.width, rect[2]), min(p.height, rect[3])
        return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None

    def move(self, pos, shift: bool = False) -> None:
        s = self._stroke
        if s is None:
            return
        pos = tuple(pos)
        if s.get("kind") in ("selrect", "selmove", "float"):
            self._drag_selection(s, pos)
            return
        if pos != s["path"][-1]:
            s["path"].append(pos)
        self._update(pos, shift)

    def release(self, pos, shift: bool = False) -> None:
        s = self._stroke
        if s is None:
            return
        pos = tuple(pos)
        kind = s.get("kind")
        if kind in ("selrect", "selmove", "float"):
            self._drag_selection(s, pos)
            self._stroke = None
            if kind == "selrect" and not s["moved"]:
                self.selection = None                      # a click without dragging deselects
            elif kind == "selmove" and self.selection is not None:
                self.selection = self._cut_to_frame(self.selection)
            self.changed.emit()
            return
        self._update(pos, shift)
        self._stroke = None
        c = self.controller
        f = c.project.frames[s["idx"]]
        if all(a.tobytes() == b.tobytes() for a, b in zip(f.layers, s["base"])):
            f.layers, f.image = s["layers"], s["image"]          # nothing changed: no Undo step
        else:
            self._push_undo(s["image"], s["layers"])
            if kind == "movesel":
                self.selection = self._cut_to_frame(self.selection) if self.selection else None
            self._edited()

    def cancel(self) -> None:
        s = self._stroke
        if s is not None and s.get("kind") in ("selrect", "selmove", "float"):
            self._stroke = None
            return
        if s is not None:
            f = self.controller.project.frames[s["idx"]]
            f.layers, f.image = s["layers"], s["image"]
            self._stroke = None
            self.frame_edited.emit(s["idx"])

    def _update(self, pos, shift: bool) -> None:
        s = self._stroke
        c = self.controller
        p = c.project
        size = s["base"][L.CORE].size
        t, o = self.tool, self.options.get(self.tool, {})
        start = s["start"]
        colour = self.draw_colour()
        top = s["targets"][0]
        if s.get("kind") == "movesel":
            dx, dy = pos[0] - start[0], pos[1] - start[1]
            new = editing.shifted_region(s["base"], s["targets"], s["rect"], dx, dy, p.transparent)
            r = s["rect"]
            self.selection = (r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy)
        elif t == "move":
            new = editing.shifted(s["base"], s["targets"], pos[0] - start[0], pos[1] - start[1], p.transparent)
        else:
            if t in ("pencil", "eraser"):
                path = [start, tools.lock_axis(start, pos)] if shift else s["path"]
                pts = tools.stroke(path, o["thickness"], o["brush"], o["pixel_perfect"])
                if t == "eraser":
                    colour = p.transparent
            elif t == "line":
                pts = tools.line_shape(start, pos, o["thickness"], o["brush"], shift)
            elif t in ("square", "circle"):
                parts = tools.rect_parts if t == "square" else tools.circle_parts
                outline, whole = parts(start, pos, o["thickness"], o["centre"], shift)
                if o["style"] == "Filled":
                    pts = whole
                elif o["style"] == "Outline + Fill":
                    base = editing.paint(s["base"], s["targets"], self.mirrored(whole - outline), self.secondary_colour(), size)
                    s = dict(s, base=base)
                    pts = outline
                else:
                    pts = outline
            elif t == "bucket":
                pts = self._fill_area(s, start)
                s["targets"] = [top]                              # a fill changes the top ticked layer only
            else:
                return
            if t != "bucket":
                pts = self.mirrored(pts)
            new = editing.paint(s["base"], s["targets"], pts, colour, size)
        editing.set_frame_layers(p, s["idx"], new)
        self.frame_edited.emit(s["idx"])

    def _fill_area(self, s, start):
        p = self.controller.project
        o = self.options["bucket"]
        if o["source"] == "Active layer":
            src = s["base"][s["targets"][0]]
        else:
            src = L.flatten(s["base"], p.transparent, self.visible)
        px = src.load()
        w, h = src.size
        return tools.flood(lambda x, y: px[x, y], w, h, start[0], start[1], o["fill"] == "Contiguous")

    # ---- selection: drag, Select All, Copy, Cut, Delete, Paste ------------------------------------------------
    def _drag_selection(self, s, pos) -> None:
        kind = s["kind"]
        if kind == "selrect":
            if pos != s["start"]:
                s["moved"] = True
            self.selection = self._frame_rect(s["start"], pos) if s["moved"] else self.selection
            self.sel_idx = s["idx"]
        elif kind == "selmove":
            dx, dy = pos[0] - s["start"][0], pos[1] - s["start"][1]
            r = s["rect"]
            self.selection = (r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy)
        else:                                               # a floating paste being dragged
            fl = self.floating
            fl["x"] = s["x"] + pos[0] - s["start"][0]
            fl["y"] = s["y"] + pos[1] - s["start"][1]
            self._render_floating()
        self.changed.emit()

    def select_all(self) -> bool:
        p = self.controller.project
        if not self.mode or p is None or not p.frames or self.floating is not None:
            return False
        self.selection, self.sel_idx = (0, 0, p.width, p.height), self.controller.selected
        self.changed.emit()
        return True

    def deselect(self) -> bool:
        if self.floating is not None or self.selection is None:
            return False
        self.selection = None
        self.changed.emit()
        return True

    def has_selection(self) -> bool:
        return self.mode and self.selection is not None and self.sel_idx == self.controller.selected

    def _can_change(self) -> bool:
        """The selection is on the frame being edited, and nothing is floating."""
        return self.has_selection() and self.controller.selected == self.idx and self.floating is None

    @property
    def can_copy(self) -> bool:
        return self.has_selection() and self.floating is None

    @property
    def can_cut(self) -> bool:
        return self._can_change()

    @property
    def can_paste(self) -> bool:
        return (self.mode and self.clipboard is not None and self.floating is None
                and self.controller.selected == self.idx)

    def _selection_targets(self) -> list[int]:
        t = self.editable()
        if not t:
            self.notice.emit(MSG_NO_LAYER)
        return t

    def copy(self) -> bool:
        if not self.can_copy:
            if self.mode and self.floating is None:
                self.notice.emit(MSG_NO_SELECTION)
            return False
        c = self.controller
        targets = self._selection_targets()
        if not targets:
            return False
        p = c.project
        base = L.layers_of(p.frames[c.selected], p.transparent)
        r = self.selection
        self.clipboard = {"w": r[2] - r[0], "h": r[3] - r[1], "layers": editing.crop_layers(base, targets, r)}
        self.changed.emit()
        return True

    def _commit_region(self, new_layers) -> None:
        """One Undo step: the frame being edited gets `new_layers`."""
        c = self.controller
        p = c.project
        f = p.frames[self.idx]
        old_image, old_layers = f.image, f.layers
        if editing.apply(p, self.idx, new_layers):
            self._push_undo(old_image, old_layers)
            self._edited()

    def delete(self) -> bool:
        if not self._can_change():
            if self.mode and self.floating is None:
                self.notice.emit(MSG_NO_SELECTION if not self.has_selection() else MSG_VIEW_ONLY)
            return False
        targets = self._selection_targets()
        if not targets:
            return False
        p = self.controller.project
        base = L.layers_of(p.frames[self.idx], p.transparent)
        self._commit_region(editing.clear_rect(base, targets, self.selection, p.transparent))
        return True

    def cut(self) -> bool:
        if not self._can_change():
            if self.mode and self.floating is None:
                self.notice.emit(MSG_NO_SELECTION if not self.has_selection() else MSG_VIEW_ONLY)
            return False
        if not self.copy():
            return False
        return self.delete()

    def paste(self) -> bool:
        c = self.controller
        p = c.project
        if not self.mode or p is None:
            return False
        if self.floating is not None:
            self.notice.emit(MSG_FLOATING)
            return False
        if self.clipboard is None:
            self.notice.emit(MSG_NOTHING_COPIED)
            return False
        if c.selected != self.idx:
            self.notice.emit(MSG_VIEW_ONLY)
            return False
        f = p.frames[self.idx]
        clip = self.clipboard
        self.floating = {"layers": dict(clip["layers"]), "w": clip["w"], "h": clip["h"], "x": 0, "y": 0,
                         "base": L.layers_of(f, p.transparent), "image": f.image, "frame_layers": f.layers}
        self.sel_idx = self.idx
        self._render_floating()
        self.notice.emit("Paste floating: drag it, press Enter to fix it in place or Esc to discard it.")
        self.changed.emit()
        return True

    def _render_floating(self) -> None:
        fl = self.floating
        p = self.controller.project
        new = editing.paste_layers(fl["base"], fl["layers"], fl["x"], fl["y"], p.transparent)
        editing.set_frame_layers(p, self.idx, new)
        self.selection = self._cut_to_frame(self._float_rect())
        self.frame_edited.emit(self.idx)

    def fix(self) -> bool:
        """Enter: a floating paste is fixed in place as one Undo step; the selection is cleared."""
        fl = self.floating
        if fl is None:
            if self.selection is not None:
                self.selection = None
                self.changed.emit()
                return True
            return False
        self.floating = None
        self.selection = None
        self._push_undo(fl["image"], fl["frame_layers"])
        self._edited()
        return True

    def escape(self) -> bool:
        """Esc: a floating paste is thrown away (the frame goes back as it was); otherwise the selection is cleared."""
        fl = self.floating
        if fl is None:
            return self.deselect()
        f = self.controller.project.frames[self.idx]
        f.layers, f.image = fl["frame_layers"], fl["image"]
        self.floating = None
        self.selection = None
        self._edited()
        return True

    def nudge(self, dx: int, dy: int) -> bool:
        """Arrow keys: move the floating paste, or the selected pixels, by one pixel."""
        if self.floating is not None:
            self.floating["x"] += dx
            self.floating["y"] += dy
            self._render_floating()
            self.changed.emit()
            return True
        if not self._can_change():
            return False
        targets = self._selection_targets()
        if not targets:
            return False
        p = self.controller.project
        base = L.layers_of(p.frames[self.idx], p.transparent)
        r = self.selection
        self._commit_region(editing.shifted_region(base, targets, r, dx, dy, p.transparent))
        self.selection = self._cut_to_frame((r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy))
        self.changed.emit()
        return True

    def frame_selected(self, index: int) -> None:
        """The Frame view moved to another frame: a selection belongs to one frame only."""
        if self.mode and self.selection is not None and self.sel_idx != index and self.floating is None:
            self.selection = None
            self.changed.emit()

    def colour_replaced(self, old, new) -> None:
        """A palette colour was replaced: copied pixels of that colour take the new colour."""
        if self.clipboard is None:
            return
        old, new = tuple(old), tuple(new)
        out = {}
        for i, im in self.clipboard["layers"].items():
            im = im.copy()
            px = im.load()
            for y in range(im.height):
                for x in range(im.width):
                    if px[x, y] == old:
                        px[x, y] = new
            out[i] = im
        self.clipboard = dict(self.clipboard, layers=out)

    # ---- actions: flip, mirror, rotate ---------------------------------------------------------------
    def can_rotate(self) -> bool:
        p = self.controller.project
        if self.floating is not None:
            return self.floating["w"] == self.floating["h"]
        if self._can_change():
            r = self.selection
            return r[2] - r[0] == r[3] - r[1]
        return p is not None and p.width == p.height

    def action(self, name: str) -> bool:
        c = self.controller
        p = c.project
        if not self.mode or p is None or not p.frames:
            return False
        targets = self.editable()
        if not targets:
            self.notice.emit(MSG_NO_LAYER)
            return False
        both = lambda b: editing.flip_vertical(editing.flip_horizontal(b, targets), targets)
        fn = {"mirror": lambda b: editing.flip_horizontal(b, targets), "flip_h": lambda b: editing.flip_horizontal(b, targets),
              "flip": lambda b: editing.flip_vertical(b, targets), "flip_v": lambda b: editing.flip_vertical(b, targets),
              "rotate_180": both,
              "rotate_left": lambda b: editing.rotate(b, targets, False),
              "rotate_right": lambda b: editing.rotate(b, targets, True)}[name]
        if name in ("rotate_left", "rotate_right") and not self.can_rotate():
            return False
        idx = c.selected
        if idx != self.idx:
            return False
        img_fn = {"mirror": Image.FLIP_LEFT_RIGHT, "flip_h": Image.FLIP_LEFT_RIGHT, "flip": Image.FLIP_TOP_BOTTOM,
                  "flip_v": Image.FLIP_TOP_BOTTOM, "rotate_180": Image.ROTATE_180, "rotate_left": Image.ROTATE_90,
                  "rotate_right": Image.ROTATE_270}[name]
        if self.floating is not None:                         # a floating paste is turned as it is
            fl = self.floating
            fl["layers"] = {i: im.transpose(img_fn) for i, im in fl["layers"].items()}
            self._render_floating()
            self.changed.emit()
            return True
        f = p.frames[idx]
        old_image, old_layers = f.image, f.layers
        if self._can_change():                                # a selection: only its pixels are turned
            new = editing.region_each(L.layers_of(f, p.transparent), targets, self.selection, lambda im: im.transpose(img_fn))
        else:
            new = fn(L.layers_of(f, p.transparent))
        if editing.apply(p, idx, new):
            self._push_undo(old_image, old_layers)
            self._edited()
            return True
        return False
