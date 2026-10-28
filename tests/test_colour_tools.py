"""v2.0.16: the colour picker in the Frame Group Preview and the RunSpriteRun window, dragging palette colours into a
new order, and + colour adding the primary colour straight away (no Apply button any more)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.app import messages
from src.app.main_window import MainWindow
from src.core.colour import level_to_8bit as lv
from src.core.project import Frame, Group, Project
from src.core.systems import get_system

BLACK, RED, GREEN, BLUE, YELLOW = (0, 0, 0), (lv(7, 3), 0, 0), (0, lv(7, 3), 0), (0, 0, lv(7, 3)), (lv(7, 3), lv(7, 3), 0)


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
    """Frame 1: black with a red pixel at (2, 3) and a green one at (5, 5). Frame 2: blue. Palette: black, red,
    green, blue (black is the transparent colour)."""
    f1 = Image.new("RGB", (8, 8), BLACK)
    f1.putpixel((2, 3), RED)
    f1.putpixel((5, 5), GREEN)
    f2 = Image.new("RGB", (8, 8), BLUE)
    return Project("P", get_system(system), 8, 8, frames=[Frame("f1_001", f1), Frame("f2_002", f2)],
                   groups=[Group("G", 0, 1)], dirty=False)


@pytest.fixture
def win(app, log):
    w = MainWindow()
    w.show()
    w.set_project(make())
    yield w
    w.controller.edit.reset()                           # leave Edit mode without its Apply / Discard question
    w.controller.project.dirty = False
    w.close()
    w.deleteLater()
    app.processEvents()


def ed(w):
    return w.panels["Colour editor"]


def pal(w):
    return w.panels["Palette panel"]


def point_of(view, x, y) -> QPoint:
    """Where sprite pixel (x, y) is drawn in a sprite view, in the view's own (logical) coordinates."""
    dpr, s, ox, oy, _w, _h = view._geometry()
    return QPoint(int((ox + x * s + s // 2) / dpr), int((oy + y * s + s // 2) / dpr))


# ---- 1. the colour picker in the Frame Group Preview and the RunSpriteRun window ---------------------------------
@pytest.mark.parametrize("panel", ["Frame Group Preview", "RunSpriteRun window"])
def test_the_picker_takes_a_colour_from_the_preview_windows(win, panel):
    view = win.panels[panel].view
    view.set_sprite(win.controller.project.frames[0].image, win.controller.project.transparent)   # frame 1 shown
    e = ed(win)
    e.eyedropper.click()
    assert e.eyedropper_armed
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, point_of(view, 2, 3))
    assert e.cols["primary"] == RED and not e.eyedropper_armed
    e.eyedropper.click()
    QTest.mouseClick(view, Qt.RightButton, Qt.NoModifier, point_of(view, 5, 5))
    assert e.cols["secondary"] == GREEN


def test_without_the_picker_a_click_in_the_preview_takes_nothing(win):
    view = win.panels["RunSpriteRun window"].view
    view.set_sprite(win.controller.project.frames[0].image, win.controller.project.transparent)
    before = dict(ed(win).cols)
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, point_of(view, 2, 3))
    assert ed(win).cols == before


# ---- 2. dragging a palette colour to another slot ------------------------------------------------------------------
def drag(grid, from_slot, to_point):
    """Press on a palette square, move with the button held, release over `to_point`."""
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent
    start = QPointF(grid.slot_rect(from_slot).center())
    end = QPointF(to_point)

    def send(kind, pos, buttons):
        ev = QMouseEvent(kind, pos, grid.mapToGlobal(pos.toPoint()), Qt.LeftButton, buttons, Qt.NoModifier)
        QApplication.sendEvent(grid, ev)

    send(QEvent.MouseButtonPress, start, Qt.LeftButton)
    send(QEvent.MouseMove, QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2 + 0.5), Qt.LeftButton)
    send(QEvent.MouseMove, end, Qt.LeftButton)
    send(QEvent.MouseButtonRelease, end, Qt.NoButton)


def test_dragging_a_colour_moves_it_and_the_others_shift_along(win):
    p = win.controller.project
    grid = pal(win).grid
    assert p.palette() == [BLACK, RED, GREEN, BLUE]
    drag(grid, 3, grid.slot_rect(0).center())                     # blue to the front
    assert p.palette() == [BLUE, BLACK, RED, GREEN]
    drag(grid, 0, grid.slot_rect(2).center())                     # and back to third place
    assert p.palette() == [BLACK, RED, BLUE, GREEN]


def test_dropping_on_a_free_slot_moves_the_colour_to_the_end(win):
    p = win.controller.project
    grid = pal(win).grid
    drag(grid, 1, grid.slot_rect(10).center())                    # slot 11 is free
    assert p.palette() == [BLACK, GREEN, BLUE, RED]


def test_moving_changes_no_pixels_and_is_one_undo_step(win):
    c = win.controller
    p = c.project
    before = [f.image.tobytes() for f in p.frames]
    drag(pal(win).grid, 3, pal(win).grid.slot_rect(0).center())
    assert [f.image.tobytes() for f in p.frames] == before and p.dirty
    c.undo()
    assert p.palette() == [BLACK, RED, GREEN, BLUE]
    c.redo()
    assert p.palette() == [BLUE, BLACK, RED, GREEN]


def test_a_plain_click_is_still_a_click_not_a_move(win):
    c = win.controller
    c.edit.begin()
    grid = pal(win).grid
    QTest.mouseClick(grid, Qt.LeftButton, Qt.NoModifier, grid.slot_rect(2).center())
    assert c.project.palette() == [BLACK, RED, GREEN, BLUE] and ed(win).cols["primary"] == GREEN


def test_the_new_order_is_saved_with_the_project(win, tmp_path):
    from src.io.project_file import open_project, save_project
    p = win.controller.project
    drag(pal(win).grid, 2, pal(win).grid.slot_rect(0).center())
    path = tmp_path / "P.rsr"
    save_project(p, path)
    assert open_project(path).palette() == [GREEN, BLACK, RED, BLUE]


def test_a_move_can_be_made_in_edit_mode(win):
    c = win.controller
    c.edit.begin()
    drag(pal(win).grid, 3, pal(win).grid.slot_rect(1).center())
    assert c.project.palette() == [BLACK, BLUE, RED, GREEN]
