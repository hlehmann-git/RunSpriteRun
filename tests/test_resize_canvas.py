"""v2.0.20: Edit > Resize Canvas. Every frame and layer gets a new canvas, centred or grounded, never cutting off what
is drawn, as one Undo step."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.app import messages
from src.app.main_window import MainWindow
from src.app.resize_dialog import ResizeDialog
from src.core import canvas
from src.core.project import Frame, Project
from src.core.systems import get_system
from src.io import settings as settings_io

T = (255, 0, 255)
RED = (255, 0, 0)
BLUE = (0, 0, 255)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def frame(label, pixels, size=8, layers=False):
    img = Image.new("RGB", (size, size), T)
    for xy, c in pixels:
        img.putpixel(xy, c)
    f = Frame(label, img)
    if layers:
        empty = Image.new("RGB", (size, size), T)
        f.layers = (empty.copy(), empty.copy(), img.copy(), empty.copy(), empty.copy())
    return f


def project(*frames, size=8):
    return Project("P", get_system("Atari ST"), size, size, transparent=T, frames=list(frames), dirty=False)


# ---- placement ---------------------------------------------------------------------------------------
def test_centred_spare_pixel_goes_right_and_bottom_both_ways():
    assert canvas.offset(8, 11) == 1             # +3: 1 on the left, 2 on the right
    assert canvas.offset(8, 5) == -1             # -3: 1 off the left, 2 off the right
    assert canvas.offset(8, 12) == 2 and canvas.offset(8, 4) == -2


def test_grounded_keeps_the_bottom_edge():
    assert canvas.offset(8, 12, grounded=True) == 4 and canvas.offset(8, 6, grounded=True) == -2


def test_growing_grounded_puts_new_rows_on_top_and_width_either_side():
    p = project(frame("a_001", [((0, 7), RED)]))                 # a foot in the bottom-left corner
    canvas.resize_project(p, 12, 12, grounded=True)
    img = p.frames[0].image
    assert (p.width, p.height) == (12, 12) and img.size == (12, 12)
    assert img.getpixel((2, 11)) == RED                          # 2 added on the left, still on the bottom row
    assert img.getpixel((0, 0)) == T and p.dirty


def test_growing_centred():
    p = project(frame("a_001", [((0, 0), RED)]))
    canvas.resize_project(p, 12, 12, grounded=False)
    assert p.frames[0].image.getpixel((2, 2)) == RED


def test_every_layer_is_resized_too():
    p = project(frame("a_001", [((3, 3), RED)], layers=True))
    canvas.resize_project(p, 10, 10, grounded=False)
    f = p.frames[0]
    assert all(im.size == (10, 10) for im in f.layers) and f.layers[2].getpixel((4, 4)) == RED


# ---- never cut off what is drawn ----------------------------------------------------------------------
def test_shrinking_into_empty_space_is_allowed():
    p = project(frame("a_001", [((3, 3), RED), ((4, 7), BLUE)]))
    assert canvas.problem(p, 6, 6, grounded=True) is None
    canvas.resize_project(p, 6, 6, grounded=True)
    img = p.frames[0].image
    assert img.size == (6, 6) and img.getpixel((2, 1)) == RED and img.getpixel((3, 5)) == BLUE


def test_a_size_that_cuts_off_pixels_is_refused_and_nothing_changes():
    p = project(frame("a_001", [((0, 4), RED)]), frame("b_002", [((4, 4), BLUE)]))
    assert canvas.clipped_frames(p, 6, 8, grounded=False) == [0]
    why = canvas.problem(p, 6, 8, grounded=False)
    assert "1 of 2 frames" in why and "at least 7 x 8" in why       # 7: the spare column comes off the right
    with pytest.raises(ValueError):
        canvas.resize_project(p, 6, 8, grounded=False)
    assert (p.width, p.height) == (8, 8) and p.frames[0].image.size == (8, 8)


def test_a_pixel_hidden_under_another_layer_still_counts():
    f = frame("a_001", [((3, 3), RED)], layers=True)
    hidden = f.layers[4].copy()
    hidden.putpixel((0, 0), BLUE)                               # only on BackGround 2, covered in the flattened picture
    f.layers = (*f.layers[:4], hidden)
    p = project(f)
    assert canvas.clipped_frames(p, 6, 6, grounded=False) == [0]


def test_smallest_size_depends_on_grounded():
    p = project(frame("a_001", [((3, 6), RED)]))                # one pixel near the bottom
    assert canvas.smallest_size(p, grounded=True) == (4, 4)     # rows come off the top only: 2 rows below it are kept
    assert canvas.smallest_size(p, grounded=False)[1] == 6      # centred: rows come off the bottom too


# ---- the window ---------------------------------------------------------------------------------------
@pytest.fixture
def win(app, monkeypatch):
    monkeypatch.setattr(messages, "warn", lambda *a, **k: None)
    w = MainWindow()
    w.show()
    w.set_project(project(frame("a_001", [((3, 7), RED)]), frame("b_002", [((4, 4), BLUE)])))
    return w


def test_resize_is_one_undo_step_and_undo_puts_the_size_back(win):
    c = win.controller
    assert c.resize_canvas(12, 10, grounded=True)
    assert (c.project.width, c.project.height) == (12, 10) and c.can_undo
    assert win.panels["Frame view"].view._image.size == (12, 10)
    c.undo()
    assert (c.project.width, c.project.height) == (8, 8) and c.project.frames[0].image.size == (8, 8)
    assert c.project.frames[0].image.getpixel((3, 7)) == RED
    c.redo()
    assert (c.project.width, c.project.height) == (12, 10)


def test_grounded_choice_is_remembered(win):
    c = win.controller
    c.resize_canvas(10, 10, grounded=False)
    assert c.settings.resize_grounded is False and settings_io.load().resize_grounded is False


def test_menu_item_is_greyed_out_in_edit_mode(win):
    assert win.act_resize.isEnabled()
    win.controller.edit.begin()
    win._update_edit_actions()
    assert not win.act_resize.isEnabled()


def test_dialog_blocks_a_size_that_would_cut_off_pixels(win):
    d = ResizeDialog(win, win.controller.project, 0, grounded=True)
    assert "4 x 4" in d.smallest.text() and not d.ok.isEnabled()      # same size: nothing to do
    d.width_box.setValue(6)
    d.height_box.setValue(6)
    assert d.ok.isEnabled() and d.error.isHidden()
    d.width_box.setValue(4)
    d.height_box.setValue(4)
    assert d.ok.isEnabled()
    d.grounded_box.setChecked(False)                                 # centred: the low pixel would be cut off
    assert not d.ok.isEnabled() and not d.error.isHidden() and "cut off pixels" in d.error.text()
    assert d.to_view.pixmap().isNull()


def test_dialog_grows_and_shows_the_change(win):
    d = ResizeDialog(win, win.controller.project, 0, grounded=True)
    d.width_box.setValue(12)
    d.height_box.setValue(10)
    assert "+4 wide" in d.change.text() and "+2 high" in d.change.text() and d.ok.isEnabled()
    assert d.chosen_size() == (12, 10) and d.grounded()
