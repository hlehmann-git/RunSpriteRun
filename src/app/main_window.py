"""M0 skeleton: an empty 1280 x 800 window with the menu bar and the region layout (section 5.1).
Panels are placeholders for now; later milestones fill them in."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QLineEdit, QMainWindow, QMenu, QPlainTextEdit,
                               QWidget)

from src.app import edit_flow, save_as_dialog
from src.app.controller import Controller
from src.app.info_bar import BAR_H, InfoBar
from src.app import messages
from src.app.frame_view import FrameViewPanel
from src.app.group_preview import GroupPreviewPanel
from src.app.edit_panel import EditPanel
from src.app.run_panel import RunPanel
from src.app.set_group_panel import SetFrameGroupPanel
from src.core import groups as group_rules
from src.core.rules import MAX_GROUPS
from src.app.colour_editor import PANEL_H, ColourEditorPanel
from src.app.palette_panel import PalettePanel
from src.app.panel import Panel
from src.app.start_project import StartProjectDialog
from src.app.timeline import TimelinePanel
from src.core.project import Project
from src.core.rules import valid_project_name
from src.app.info_dialogs import AboutDialog, HelpDialog, ProjectInformationDialog
from src.app.settings_dialog import SettingsDialog
from src.app.shrink_dialog import WARNING, ShrinkDialog
from src.core.shrink import new_size, percent_label, shrink_project
from src.app.blank_sheet_dialog import BlankSheetDialog
from src.app.export_dialog import ExportDialog
from src.io import paths
from src.io.project_file import ProjectFileError, open_project
from src.io.save import save_whole
from PySide6.QtWidgets import QFileDialog
import shutil
from pathlib import Path

EDIT_FRAME_H = 584                      # the Frame view panel in Edit mode (512 px picture)
EDIT_PALETTE_X = 880                    # the colour card, moved over in Edit mode
DESIGN_W, DESIGN_H = 1280, 948          # 800 + the 24 px information bar under the menu bar + 124 px of spare space (1.b)
RUN_KEYS = {getattr(Qt, f"Key_{c}"): c for c in "WASD123456"}     # digits: top row and keypad share these codes

# name, x, y, w, h  (logical pixels, section 5.1 region table)
REGIONS = [
    ("Frame view", 16, 44, 288, 324),
    ("Frame Group Preview", 320, 44, 288, 324),
    ("RunSpriteRun window", 624, 44, 288, 324),
    ("Palette panel", 928, 44, 336, 70),       # card top half; taller for 32 or 64 slots (placed in code)
    ("Set Frame Group", 16, 384, 544, 208),
    ("Keys", 576, 384, 688, 208),
    ("Colour editor", 928, 114, 336, 204),    # card bottom half, directly under the palette
    ("Timeline and frames", 16, 608, 1248, 234),
]


TOOL_KEYS = {Qt.Key_P: "pencil", Qt.Key_E: "eraser", Qt.Key_B: "bucket", Qt.Key_S: "select", Qt.Key_M: "move",
             Qt.Key_L: "line", Qt.Key_R: "square", Qt.Key_O: "circle"}      # Edit mode only


class MainWindow(QMainWindow):
    def __init__(self, settings=None) -> None:
        super().__init__()
        self.setWindowTitle("RunSpriteRun")
        self._large = False                                       # Edit mode layout: a larger Frame view
        self.setMinimumSize(DESIGN_W, DESIGN_H)
        self.resize(DESIGN_W, DESIGN_H)
        self._build_menus()
        canvas = QWidget(self)
        canvas.setFixedSize(DESIGN_W, DESIGN_H - 32)
        self.controller = Controller(self, settings)
        self.info_bar = InfoBar(canvas, self.controller)
        self.info_bar.setGeometry(0, 0, DESIGN_W, BAR_H)
        self.setCentralWidget(canvas)
        real = {
            "Frame view": lambda: FrameViewPanel(canvas, self.controller),
            "Frame Group Preview": lambda: GroupPreviewPanel(canvas, self.controller),
            "RunSpriteRun window": lambda: RunPanel(canvas, self.controller),
            "Keys": lambda: EditPanel(canvas, self.controller),
            "Set Frame Group": lambda: SetFrameGroupPanel(canvas, self.controller),
            "Palette panel": lambda: PalettePanel(canvas, self.controller),
            "Colour editor": lambda: ColourEditorPanel(canvas, self.controller),
            "Timeline and frames": lambda: TimelinePanel(canvas, self.controller),
        }
        self.panels: dict[str, Panel] = {}
        for name, x, y, w, h in REGIONS:
            panel = real[name]() if name in real else Panel(name, canvas)   # the rest are placeholders
            panel.setGeometry(x, y - 32 + BAR_H, w, h)   # y in the table includes the 32 px menu bar; the info bar is under it
            self.panels[name] = panel
        self.panels["Palette panel"].height_changed.connect(self._place_colour_card)
        self._place_colour_card(self.panels["Palette panel"].wanted_height())
        self.project: Project | None = None
        self.set_frame_group = self.panels["Set Frame Group"]
        self.set_frame_group.current_group_changed.connect(lambda _name: self._update_group_actions())
        self.controller.frames_changed.connect(self._update_group_actions)
        self.controller.history_changed.connect(self._update_edit_actions)
        self.controller.edit.changed.connect(self._edit_mode_changed)
        self.controller.frames_changed.connect(self._update_save_action)
        self.controller.history_changed.connect(self._update_save_action)
        self.set_project_active(False)

        self.panels["RunSpriteRun window"].toggle_requested.connect(self.toggle_run)
        self.f5 = QShortcut(QKeySequence("F5"), self)             # start / stop RunSpriteRun (FR-3.3)
        self.f5.activated.connect(self.toggle_run)
        QApplication.instance().installEventFilter(self)

    def _place_colour_card(self, palette_h: int) -> None:
        """The palette and the colour editor are one card: the colour editor sits directly under the palette,
        which is taller for 32 or 64 slots."""
        top = 44 - 32 + BAR_H
        x = EDIT_PALETTE_X if self._large else 928
        pal, ed = self.panels["Palette panel"], self.panels["Colour editor"]
        pal.setGeometry(x, top, 336, palette_h)
        ed.setGeometry(x, top + palette_h, 336, PANEL_H)

    def _set_layout(self, large: bool) -> None:
        """Edit mode makes the Frame view larger (512 px): the Frame Group Preview and the colour card move over,
        Set Frame Group and the RunSpriteRun window are hidden, and the timeline moves down. Leaving restores it."""
        if large == self._large:
            return
        self._large = large
        dy = BAR_H - 32
        g = lambda name, x, y, w, h: self.panels[name].setGeometry(x, y + dy, w, h)
        self.panels["Frame view"].set_large(large)
        if large:
            g("Frame view", 16, 44, 544, EDIT_FRAME_H)
            g("Frame Group Preview", 576, 44, 288, 324)
            g("Timeline and frames", 16, 44 + EDIT_FRAME_H + 16, 1248, 234)
        else:
            for name, x, y, w, h in REGIONS:
                if name in ("Frame view", "Frame Group Preview", "Timeline and frames"):
                    g(name, x, y, w, h)
        for name in ("Set Frame Group", "RunSpriteRun window"):
            self.panels[name].setVisible(not large)
        self._place_colour_card(self.panels["Palette panel"].wanted_height())

    def _action(self, menu: QMenu, text: str, shortcut: str | None = None) -> QAction:
        act = menu.addAction(text)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        return act

    def _build_menus(self) -> None:
        bar = self.menuBar()
        bar.setFixedHeight(32)                      # section 5.1: menu bar is 1280 x 32
        self.menu_file = bar.addMenu("File")
        self.menu_edit = bar.addMenu("Edit")
        self.menu_group = bar.addMenu("Group")
        self.menu_help = bar.addMenu("Help")
        self.menu_about = bar.addMenu("About")
        a = self._action
        self.act_new = a(self.menu_file, "New Project", "Ctrl+N")
        self.act_open = a(self.menu_file, "Open Project", "Ctrl+O")
        self.act_save = a(self.menu_file, "Save", "Ctrl+S")
        self.act_save_as = a(self.menu_file, "Save As")
        self.act_info = a(self.menu_file, "Project Information")
        self.act_export = a(self.menu_file, "Export", "Ctrl+E")
        self.act_blank_sheet = a(self.menu_file, "Create Blank Sprite Sheet")
        self.act_settings = a(self.menu_file, "Settings", "Ctrl+,")
        self.act_exit = a(self.menu_file, "Exit")
        self.act_undo = a(self.menu_edit, "Undo", "Ctrl+Z")
        self.act_redo = a(self.menu_edit, "Redo", "Ctrl+Y")
        self.menu_edit.addSeparator()
        self.act_shrink = a(self.menu_edit, "Shrink Sprite")
        self.act_new_group = a(self.menu_group, "New Group", "Ctrl+G")
        self.act_delete_group = a(self.menu_group, "Delete Group")
        self.act_help = a(self.menu_help, "RunSpriteRun Help (F1)", "F1")
        self.act_about = a(self.menu_about, "About RunSpriteRun")
        self.act_exit.triggered.connect(self.close)
        self.act_new_group.triggered.connect(lambda: self.set_frame_group.new_group())
        self.act_delete_group.triggered.connect(self.delete_group)
        self.act_undo.triggered.connect(lambda: self.controller.edit.undo() if self.controller.edit.mode else self.controller.undo())
        self.act_redo.triggered.connect(lambda: self.controller.edit.redo() if self.controller.edit.mode else self.controller.redo())
        self.act_shrink.triggered.connect(self.shrink_sprite)
        self.act_new.triggered.connect(self.new_project)
        self.act_open.triggered.connect(self.open_project_dialog)
        self.act_save.triggered.connect(self.save)
        self.act_save_as.triggered.connect(self.save_as)
        self.act_info.triggered.connect(self.show_information)
        self.act_export.triggered.connect(self.show_export)
        self.act_blank_sheet.triggered.connect(self.show_blank_sheet)
        self.act_settings.triggered.connect(self.show_settings)
        self.act_help.triggered.connect(lambda: HelpDialog(self).exec())
        self.act_about.triggered.connect(lambda: AboutDialog(self).exec())

    # ---- RunSpriteRun: F5 and the keys -----------------------------------------------------------------
    def toggle_run(self) -> None:
        if self.controller.project is None:
            return
        if not self.controller.running:
            self._clear_text_focus()                       # keys only work when no text box has focus
        self.controller.toggle_run()

    @staticmethod
    def _text_focus() -> bool:
        w = QApplication.focusWidget()
        return isinstance(w, (QLineEdit, QAbstractSpinBox, QPlainTextEdit)) or (
            isinstance(w, QComboBox) and w.isEditable())

    def _clear_text_focus(self) -> None:
        if self._text_focus():
            QApplication.focusWidget().clearFocus()

    def eventFilter(self, obj, event) -> bool:
        t = event.type()
        if t in (QEvent.KeyPress, QEvent.KeyRelease) and event.key() in RUN_KEYS:
            if event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier):
                return False
            key = RUN_KEYS[event.key()]
            if t == QEvent.KeyRelease:
                if not event.isAutoRepeat() and self.controller.key_release(key):
                    return True
                return False
            if not self._text_focus() and self.isActiveWindow():
                if self.controller.running:
                    if not event.isAutoRepeat():          # keyboard auto-repeat is ignored
                        self.controller.key_press(key)
                    return True
                if not event.isAutoRepeat() and self.controller.start_with_key(key):
                    return True                           # a key with a group starts RunSpriteRun (as F5 does)
        elif t == QEvent.KeyPress and self.controller.edit.mode and self._edit_key(event):
            return True
        elif t in (QEvent.WindowDeactivate, QEvent.ApplicationDeactivate) and obj is self:
            self.controller.release_all_keys()            # no key can stay "held" when the window loses focus
        return False

    def _edit_key(self, event) -> bool:
        """Keys of the Select tool in Edit mode: Ctrl+A, C, X, V, Delete, Enter (fix a paste), Esc (discard), arrows."""
        if not self.isActiveWindow() or QApplication.activeModalWidget() is not None or self._text_focus():
            return False
        e = self.controller.edit
        key, mods = event.key(), event.modifiers()
        ctrl = bool(mods & Qt.ControlModifier)
        if ctrl and not (mods & (Qt.AltModifier | Qt.ShiftModifier)):
            fn = {Qt.Key_A: e.select_all, Qt.Key_C: e.copy, Qt.Key_X: e.cut, Qt.Key_V: e.paste}.get(key)
            if fn is not None:
                fn()
                return True
            return False
        if mods & (Qt.AltModifier | Qt.MetaModifier):
            return False
        tool = TOOL_KEYS.get(key) if not (mods & Qt.ShiftModifier) and not event.isAutoRepeat() else None
        if tool is not None:
            e.set_tool(tool)
            return True
        if key == Qt.Key_Delete:
            e.delete()
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter) and (e.floating is not None or e.selection is not None):
            return e.fix()
        if key == Qt.Key_Escape and (e.floating is not None or e.selection is not None):
            return e.escape()
        step = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}.get(key)
        if step is not None and (e.floating is not None or e.can_cut):
            return e.nudge(*step)
        return False

    def show_start_project(self) -> bool:
        """Show the modal Start Project dialog. Returns True if a project was created or opened."""
        dialog = StartProjectDialog(self)
        if dialog.exec() == StartProjectDialog.Accepted and dialog.project is not None:
            self.set_project(dialog.project)
            return True
        return False

    # ---- File menu: new, open, save, close (FR-4.4) ------------------------------------------------
    def confirm_close(self) -> bool:
        """Unsaved changes: ask Save / Don't Save / Cancel. Returns False if the user cancels (or a save fails)."""
        if not edit_flow.leave(self, self.controller.edit):        # Edit mode: Apply, Discard or Keep editing first
            return False
        p = self.controller.project
        if p is None or not p.dirty:
            return True
        answer = messages.save_changes(self, p.name)
        if answer == "cancel":
            return False
        if answer == "save":
            return self.save()
        return True

    def _editing(self) -> bool:
        """True (after saying why) while Edit mode is on: these commands wait until the owner leaves it."""
        if self.controller.edit.mode:
            messages.info(self, edit_flow.MSG_LEAVE_FIRST, edit_flow.MSG_LEAVE_DETAIL)
            return True
        return False

    def new_project(self) -> None:
        if self._editing():
            return
        if self.confirm_close():
            self.show_start_project()

    def open_project_dialog(self) -> None:
        if self._editing():
            return
        if not self.confirm_close():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", str(paths.projects_folder()),
                                              "RunSpriteRun projects (*.rsr)")
        if not path:
            return
        try:
            project = open_project(path)
        except ProjectFileError:
            messages.warn(self, f"{Path(path).name} could not be opened. It may be damaged or saved by a "
                                "different version of RunSpriteRun.")
            return                                       # the open project stays as it was
        self.set_project(project)

    def save(self) -> bool:
        p = self.controller.project
        if p is None or self._editing():
            return False
        if p.file_path is None or Path(p.file_path).parent.name != p.name:
            return self.save_as()                        # a file that is not in its own project folder is saved as a new project
        return self._write(p, p.file_path)

    def save_as(self) -> bool:
        """Save As makes a new project: a new name and a new project folder inside the chosen parent folder,
        with the .rsr saved inside it (FR-4.4, FR-5.3)."""
        p = self.controller.project
        if p is None or self._editing():
            return False
        name, folder = p.name, str(paths.projects_folder())
        while True:
            answer = save_as_dialog.ask(self, name, folder)
            if answer is None:
                return False
            name, folder = answer
            if not valid_project_name(name):
                messages.warn(self, "Project names can only use letters, numbers, - and _ (no spaces).")
                continue                                          # the box opens again
            target = paths.project_folder(Path(folder), name)
            if target.exists():
                messages.warn(self, f"A project called {name} already exists in {folder}. Choose another name.")
                continue
            break
        try:
            target.mkdir(parents=True)
        except OSError as e:
            messages.warn(self, f"{name} could not be saved. {e.strerror or e}")
            return False
        old_name, old_written, old_path = p.name, list(p.written_files), p.file_path
        p.name = name
        p.written_files = []                              # a new folder starts empty: nothing to clean up in it
        if not self._write(p, str(target / f"{name}.rsr")):
            p.name, p.written_files, p.file_path = old_name, old_written, old_path
            shutil.rmtree(target, ignore_errors=True)      # the folder was created by this Save As
            return False
        self.info_bar.refresh()
        return True

    def _write(self, p: Project, path: str) -> bool:
        try:
            save_whole(p, path)
        except OSError as e:
            messages.warn(self, f"{Path(path).name} could not be saved. {e.strerror or e}")
            return False                                 # the project stays open and unsaved
        self.controller.clear_history()                  # saving clears undo (FR-2.2)
        self._update_save_action()
        return True

    def closeEvent(self, event) -> None:
        if self.confirm_close():
            event.accept()
        else:
            event.ignore()

    def show_information(self) -> None:
        if self.controller.project is not None:
            ProjectInformationDialog(self, self.controller.project, self.controller).exec()

    def show_export(self) -> None:
        if self.controller.project is not None and not self._editing():
            ExportDialog(self, self.controller.project).exec()

    def show_blank_sheet(self) -> None:
        BlankSheetDialog(self).exec()          # needs no project (FR-4.9)

    def shrink_sprite(self) -> None:
        """Edit > Shrink Sprite: ask how small, ask again, then shrink every frame. It cannot be undone, so the Undo
        history is cleared; the project counts as unsaved."""
        c = self.controller
        p = c.project
        if p is None or c.edit.mode or not p.frames:
            return
        dlg = ShrinkDialog(self, p.width, p.height)
        if not dlg.exec():
            return
        pct = dlg.percent()
        w, h = new_size(p.width, p.height, pct)
        if not messages.choose(self, f"Shrink every frame to {percent_label(pct)} of its size ({w} x {h} pixels)?",
                               WARNING, "Shrink", "Cancel"):
            return
        selected = c.selected
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            shrink_project(p, pct)
        finally:
            QApplication.restoreOverrideCursor()
        self.set_project(p)                              # every panel follows the new size; the Undo history starts again
        c.select(min(selected, len(p.frames) - 1))
        p.dirty = True
        self._update_save_action()

    def show_settings(self) -> None:
        if self.controller.project is not None:
            SettingsDialog(self).exec()

    def set_project(self, project: Project) -> None:
        self.project = project
        self.controller.set_project(project)
        self.set_project_active(True)
        self._update_save_action()

    def set_project_active(self, active: bool) -> None:
        """Before a project exists the layout is shown greyed out (section 5.3 On launch)."""
        for panel in self.panels.values():
            panel.setEnabled(active)
        if active:
            self._edit_mode_changed()
        for act in (self.act_open, self.act_save, self.act_save_as, self.act_info, self.act_export,
                    self.act_settings, self.act_help, self.act_about,
                    self.act_new_group, self.act_delete_group):
            act.setEnabled(active)
        self._update_group_actions()
        self._update_edit_actions()
        self._update_save_action()

    def _edit_mode_changed(self) -> None:
        """Edit mode greys out Set Frame Group and the RunSpriteRun window, and the Group menu."""
        active = self.controller.project is not None
        editing = self.controller.edit.mode
        self._set_layout(editing)
        for name in ("Set Frame Group", "RunSpriteRun window"):
            self.panels[name].setEnabled(active and not editing)
        self._update_group_actions()
        self._update_edit_actions()

    def _update_save_action(self) -> None:
        """Save is greyed out when there is nothing new to save; a never-saved project can always be saved."""
        p = self.controller.project
        self.act_save.setEnabled(p is not None and (p.dirty or p.file_path is None))

    def _update_edit_actions(self) -> None:
        """Undo and Redo are greyed out when there is nothing to undo or redo (FR-2.2)."""
        e = self.controller.edit
        self.act_undo.setEnabled(e.can_undo if e.mode else self.controller.can_undo)
        self.act_redo.setEnabled(e.can_redo if e.mode else self.controller.can_redo)
        p = self.controller.project
        self.act_shrink.setEnabled(p is not None and bool(p.frames) and not e.mode)    # not while editing

    # ---- Group menu ----------------------------------------------------------------------------
    def _update_group_actions(self) -> None:
        """Items that cannot apply are greyed out (section 5.1 Menus)."""
        p = self.controller.project
        active = p is not None and not self.controller.edit.mode       # Group menu is off while editing
        self.act_new_group.setEnabled(active and len(p.groups) < MAX_GROUPS)
        self.act_delete_group.setEnabled(active and self.set_frame_group.current is not None)

    def delete_group(self) -> None:
        name = self.set_frame_group.current
        if name is None or self.controller.project is None:
            return
        if not messages.choose(self, group_rules.msg_delete_group(name), "", "Delete", "Cancel"):
            return
        affected = self.controller.delete_group(name)
        if affected:
            messages.info(self, group_rules.msg_rules_reset(name, affected))

