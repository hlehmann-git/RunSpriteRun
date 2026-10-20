"""The palette keeps unused colours, Delete colour, and the "add new colour" mode (v2.0.8)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import zipfile

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from src.app import messages
from src.app.main_window import MainWindow
from src.core import editing, reduce_palette
from src.core.colour import level_to_8bit as lv
from src.core.project import Frame, Project
from src.core.systems import get_system
from src.io.project_file import open_project, save_project

RED, GREEN, BLUE, YELLOW = (lv(7, 3), 0, 0), (0, lv(7, 3), 0), (0, 0, lv(7, 3)), (lv(7, 3), lv(7, 3), 0)
BLACK = (0, 0, 0)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def log(monkeypatch):
    out = {"warn": [], "choose": []}
    monkeypatch.setattr(messages, "warn", lambda p, t, d=None: out["warn"].append((t, d)))
    monkeypatch.setattr(messages, "info", lambda p, t, d=None: None)
    monkeypatch.setattr(messages, "choose", lambda p, t, d, y, n: (out["choose"].append(t), True)[1])
    return out


def make(system="Atari ST"):
    img = Image.new("RGB", (4, 4), BLACK)
    img.putpixel((1, 1), RED)
    img.putpixel((2, 2), GREEN)
    img.putpixel((3, 3), BLUE)
    return Project("P", get_system(system), 4, 4, frames=[Frame("f_001", img), Frame("g_002", img.copy())], dirty=False)


@pytest.fixture
def win(app, log):
    for stray in QApplication.topLevelWidgets():          # dialogs other test files left open would catch the Esc key
        if isinstance(stray, QDialog) and stray.isVisible():
            stray.hide()
    w = MainWindow()
    w.show()
    w.set_project(make())
    return w


def paint_over(p, colour, with_colour):
    for f in p.frames:
        f.image = f.image.copy()                       # images are never changed in place (Undo keeps the old ones)
        px = f.image.load()
        for y in range(4):
            for x in range(4):
                if px[x, y] == colour:
                    px[x, y] = with_colour


# ---- the palette keeps unused colours -----------------------------------------------------------
def test_unused_colour_stays_in_its_slot():
    p = make()
    before = p.palette()
    assert before == [BLACK, RED, GREEN, BLUE]
    paint_over(p, RED, BLACK)                          # no frame uses red any more
    assert p.palette() == before                       # it stays, in the same slot
    assert not p.colour_is_used(RED)


def test_new_colour_goes_after_the_kept_ones():
    p = make()
    p.palette()
    paint_over(p, RED, BLACK)
    p.frames[0].image.putpixel((0, 0), YELLOW)
    assert p.palette() == [BLACK, RED, GREEN, BLUE, YELLOW]


def test_kept_colours_count_toward_the_limit():
    p = make()                                          # Atari ST: 16 colours
    p.palette()
    paint_over(p, RED, BLACK)                           # red is kept although unused
    free = 16 - len(p.palette())
    added = 0
    for r in range(8):
        for g in range(8):
            if editing.add_colour(p, (lv(r, 3), lv(g, 3), lv(2, 3))):
                added += 1
    assert added == free and len(p.palette()) == 16     # the kept red took one of the 16 places


def test_save_and_open_keeps_unused_colours_and_order(tmp_path):
    p = make()
    p.palette()
    paint_over(p, GREEN, BLACK)
    save_project(p, tmp_path / "k.rsr")
    back = open_project(tmp_path / "k.rsr")
    assert back.palette() == [BLACK, RED, GREEN, BLUE]


def test_an_older_file_opens_with_the_old_order(tmp_path):
    p = make()
    save_project(p, tmp_path / "o.rsr")
    path = tmp_path / "old.rsr"
    with zipfile.ZipFile(tmp_path / "o.rsr") as zin, zipfile.ZipFile(path, "w") as zout:
        for item in zin.namelist():
            data = zin.read(item)
            if item == "project.json":
                meta = json.loads(data)
                meta.pop("palette_saved")
                meta["extra_colours"] = [list(YELLOW)]
                data = json.dumps(meta).encode()
            zout.writestr(item, data)
    assert open_project(path).palette() == [BLACK, RED, GREEN, BLUE, YELLOW]


def test_undo_restores_the_palette_with_the_frames(win):
    c = win.controller
    p = c.project
    before = c.checkpoint()
    paint_over(p, RED, BLACK)
    c.commit(before)
    assert RED in p.palette()
    c.undo()
    assert p.colour_is_used(RED) and RED in p.palette()


# ---- Delete colour -----------------------------------------------------------------------------
def test_delete_colour_rules(win):
    c = win.controller
    p = c.project
    assert "used" in editing.can_delete_colour(p, RED)
    assert "transparent" in editing.can_delete_colour(p, p.transparent)
    paint_over(p, RED, BLACK)
    assert editing.can_delete_colour(p, RED) is None
    assert c.delete_colour(p.palette().index(RED))
    assert p.palette() == [BLACK, GREEN, BLUE]          # the squares after it move up
    c.undo()
    assert p.palette() == [BLACK, RED, GREEN, BLUE]     # one Undo step


def test_fixed_palette_cannot_delete():
    p = make("Commodore 64")
    assert editing.can_delete_colour(p, p.palette()[-1]) is not None


# ---- add new colour mode -----------------------------------------------------------------------
def ed(w):
    return w.panels["Colour editor"]


def pal(w):
    return w.panels["Palette panel"]


def test_add_mode_locks_everything_and_arms_the_pipette(win):
    c = win.controller
    ed(win).add_btn.click()
    assert c.add_mode
    assert ed(win).eyedropper_armed and ed(win).apply_btn.isEnabled()
    assert pal(win).grid.add_slot == len(c.project.palette())
    assert not win.panels["Timeline and frames"].isEnabled()
    assert not win.panels["Set Frame Group"].isEnabled()
    assert not win.act_save.isEnabled()
    assert not ed(win).t_box.isEnabled()


def test_escape_cancels(win):
    c = win.controller
    ed(win).add_btn.click()
    QTest.keyClick(win, Qt.Key_Escape)
    assert not c.add_mode and not ed(win).apply_btn.isEnabled()
    assert win.panels["Timeline and frames"].isEnabled() and win.act_save.isEnabled()
    assert pal(win).grid.add_slot is None


def test_apply_adds_to_the_next_free_slot_and_ends_the_mode(win):
    c = win.controller
    p = c.project
    n = len(p.palette())
    ed(win).add_btn.click()
    ed(win).sliders[0].setValue(7)
    ed(win).sliders[1].setValue(7)                      # yellow
    ed(win).apply_btn.click()
    assert not c.add_mode
    assert p.palette()[n] == YELLOW and len(p.palette()) == n + 1
    c.undo()
    assert YELLOW not in p.palette()                    # one Undo step (outside Edit mode)


def test_apply_of_a_colour_already_in_the_palette_shows_the_error(win, log):
    c = win.controller
    ed(win).add_btn.click()
    ed(win).sliders[0].setValue(7)
    ed(win).sliders[1].setValue(0)
    ed(win).sliders[2].setValue(0)                      # red: already there
    ed(win).apply_btn.click()
    assert c.add_mode and log["warn"] and "already in the palette" in log["warn"][-1][0]
    assert len(c.project.palette()) == 4


def test_palette_squares_do_nothing_while_adding(win):
    c = win.controller
    ed(win).add_btn.click()
    g = pal(win).grid
    before = ed(win).colour
    QTest.mouseClick(g, Qt.LeftButton, Qt.NoModifier, g.slot_rect(1).center())
    assert ed(win).colour == before and c.add_mode


def test_the_button_is_off_for_fixed_systems_and_full_palettes(app, log):
    w = MainWindow()
    w.show()
    w.set_project(make("Commodore 64"))
    assert not ed(w).add_btn.isEnabled()
    w.set_project(make("Atari ST"))
    assert ed(w).add_btn.isEnabled()
    p = w.controller.project
    p.extra_colours = [(i % 4 * 85, i // 4 % 4 * 85, i // 16 * 85) for i in range(16)]
    w.controller.frames_changed.emit()
    assert not ed(w).add_btn.isEnabled()


def test_edit_mode_plus_colour_button_starts_the_same_mode(win):
    c = win.controller
    c.edit.begin()
    keys = win.panels["Keys"]
    keys.tool_buttons["plus"].click()
    assert c.add_mode and keys.tool_buttons["plus"].selected
    assert not keys.tool_buttons["pencil"].isEnabled()
    ed(win).sliders[0].setValue(7)
    ed(win).sliders[1].setValue(7)
    ed(win).apply_btn.click()
    assert not c.add_mode and c.edit.tool == "pencil" and YELLOW in c.project.palette()
    assert keys.tool_buttons["pencil"].isEnabled()


# ---- the right-click menu and Reduce Palette -------------------------------------------------------
def test_reduce_palette_drops_unused_colours_first():
    p = make()
    p.palette()
    paint_over(p, RED, BLACK)                          # red is kept but unused
    lo, hi = reduce_palette.target_range(p)
    mapping = reduce_palette.reduce_project(p, hi)     # one fewer colour
    assert RED not in p.palette() and GREEN in p.palette() and BLUE in p.palette()
