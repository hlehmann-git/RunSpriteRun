"""v2.0.19: the transparent colour shown as a checkerboard, Toggle Solid background (X box and Ctrl+B), and the
larger From / To pictures in Set Frame Group with the group colour around them."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.app import messages
from src.app.main_window import MainWindow
from src.app.render import (CHECKER_CELL, CHECKER_DARK, CHECKER_LIGHT, GRID, GRID_ON_CHECKER, render_sprite_at,
                            render_window, scaled_sprite)
from src.core.project import Frame, Group, Project
from src.core.systems import get_system
from src.io import settings as settings_io

T = (255, 0, 255)                   # the transparent colour in these tests
RED = (255, 0, 0)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def sprite(size=12):
    """A sprite that is all transparent except pixel (0, 0)."""
    img = Image.new("RGB", (size, size), T)
    img.putpixel((0, 0), RED)
    return img


def square_at(big, scale, x, y):
    """The colour of sprite pixel (x, y) in a scaled image, read from the middle of its cell."""
    return big.getpixel((x * scale + scale // 2, y * scale + scale // 2))


# ---- drawing --------------------------------------------------------------------------------------
def test_checkerboard_squares_cover_three_by_three_sprite_pixels():
    big = scaled_sprite(sprite(), T, 120, 120, grid=False, checker=True)            # scale 10
    n = CHECKER_CELL
    assert square_at(big, 10, 0, 0) == RED                                          # a real pixel is untouched
    assert square_at(big, 10, 1, 1) == square_at(big, 10, n - 1, n - 1) == CHECKER_LIGHT
    assert square_at(big, 10, n, 0) == square_at(big, 10, 0, n) == CHECKER_DARK
    assert square_at(big, 10, n, n) == CHECKER_LIGHT
    assert T not in {c for _, c in big.getcolors()}


def test_checkerboard_grows_with_the_zoom():
    small = scaled_sprite(sprite(), T, 24, 24, grid=False, checker=True)            # scale 2
    large = scaled_sprite(sprite(), T, 96, 96, grid=False, checker=True)            # scale 8
    for x, y in ((1, 1), (4, 1), (7, 7), (10, 4)):
        assert square_at(small, 2, x, y) == square_at(large, 8, x, y)


def test_off_by_default_and_never_in_the_timeline_boxes():
    assert square_at(scaled_sprite(sprite(), T, 120, 120, grid=False), 10, 5, 5) == T
    hidden = scaled_sprite(sprite(), T, 120, 120, grid=False, hide=True, checker=True)
    assert square_at(hidden, 10, 5, 5) == (0, 0, 0)


def test_a_panned_view_keeps_the_squares_on_the_same_sprite_pixels():
    img = sprite(40)
    full = scaled_sprite(img, T, 400, 400, grid=False, checker=True)                 # scale 10, nothing cut off
    panned = render_window(img, T, 200, 200, 10, -70, -40, grid=False, checker=True)  # sprite pixel (7, 4) at the top left
    for x, y in ((7, 4), (8, 4), (9, 5), (12, 9), (20, 15)):
        vx, vy = (x - 7) * 10 + 5, (y - 4) * 10 + 5
        assert panned.getpixel((vx, vy)) == square_at(full, 10, x, y)


def test_grid_lines_are_softer_over_the_checkerboard():
    big = scaled_sprite(sprite(), T, 120, 120, grid=True, checker=True)
    assert big.getpixel((9, 5)) == GRID                    # the cell of the real pixel keeps its black line
    assert big.getpixel((29, 5)) == GRID_ON_CHECKER        # a transparent cell's line is softer
    plain = scaled_sprite(sprite(), T, 120, 120, grid=True)
    assert plain.getpixel((29, 5)) == GRID                 # solid background: black as before


def test_runspritterun_zoom_can_show_the_checkerboard():
    out = render_sprite_at(sprite(), T, 120, 120, 10, checker=True)
    assert out.getpixel((15, 15)) == CHECKER_LIGHT and out.getpixel((5, 5)) == RED


# ---- the setting ----------------------------------------------------------------------------------
def test_solid_background_setting_is_saved_and_defaults_to_off(tmp_path):
    path = tmp_path / "s.json"
    assert settings_io.load(path).solid_background is False
    settings_io.save(settings_io.Settings(solid_background=True), path)
    assert settings_io.load(path).solid_background is True
    path.write_text('{"solid_background": "yes"}', encoding="utf-8")
    assert settings_io.load(path).solid_background is False                          # a bad value falls back


# ---- the window -----------------------------------------------------------------------------------
def project():
    frames = [Frame(f"f{i + 1}_{i + 1:03d}", sprite(8)) for i in range(4)]
    return Project("P", get_system("Atari ST"), 8, 8, transparent=T, frames=frames,
                   groups=[Group("Walk", 0, 2, colour=(90, 180, 120))], dirty=False)


@pytest.fixture
def win(app, monkeypatch):
    monkeypatch.setattr(messages, "warn", lambda *a, **k: None)
    monkeypatch.setattr(messages, "choose", lambda *a, **k: True)
    w = MainWindow()
    w.show()
    w.set_project(project())
    return w


def big_views(w):
    return [w.panels["Frame view"].view, w.panels["Frame Group Preview"].view, w.panels["RunSpriteRun window"].view]


def test_the_big_views_show_the_checkerboard_and_the_small_pictures_do_not(win):
    assert all(v.checker for v in big_views(win))
    sfg = win.panels["Set Frame Group"]
    assert not sfg.from_view.checker and not sfg.to_view.checker


def test_the_x_box_toggles_solid_background_and_is_remembered(win):
    box = win.panels["Colour editor"].solid_box
    assert not box.isChecked()                                     # empty box: the checkerboard is showing
    box.click()
    assert box.isChecked() and win.controller.settings.solid_background
    assert not any(v.checker for v in big_views(win))
    assert settings_io.load().solid_background is True             # kept for the next start
    box.click()
    assert not win.controller.settings.solid_background and all(v.checker for v in big_views(win))


def test_ctrl_b_toggles_it_and_the_x_box_follows(win):
    box = win.panels["Colour editor"].solid_box
    win.activateWindow()
    QApplication.processEvents()
    QTest.keyClick(win, Qt.Key_B, Qt.ControlModifier)
    assert win.controller.settings.solid_background and box.isChecked()
    assert not any(v.checker for v in big_views(win))
    win.act_solid_bg.trigger()
    assert not win.controller.settings.solid_background and not box.isChecked()


def test_ctrl_b_in_edit_mode_does_not_pick_the_bucket(win):
    c = win.controller
    c.edit.begin()
    tool = c.edit.tool
    win.act_solid_bg.trigger()
    assert c.settings.solid_background and c.edit.tool == tool


def test_the_colour_card_is_taller_and_ends_level_with_the_frame_view(win):
    ed = win.panels["Colour editor"]
    fv = win.panels["Frame view"]
    win.set_project(Project("A", get_system("Amiga"), 8, 8, transparent=T, frames=[Frame("a_001", sprite(8))]))
    assert ed.geometry().bottom() <= fv.geometry().bottom()
    assert ed.solid_box.geometry().bottom() < ed.height()


# ---- Set Frame Group pictures -----------------------------------------------------------------------
def test_from_and_to_pictures_are_bigger_with_the_numbers_under_them(win):
    s = win.panels["Set Frame Group"]
    s._chosen(s.chooser.findText("Walk"))
    assert s.from_view.width() == s.to_view.width() == 96
    assert s.from_box.y() > s.from_view.geometry().bottom() and s.to_box.y() > s.to_view.geometry().bottom()
    assert s.from_box.geometry().bottom() == s.apply_btn.geometry().bottom()


def test_the_pictures_have_the_group_colour_around_them(win):
    s = win.panels["Set Frame Group"]
    s._chosen(s.chooser.findText("Walk"))
    assert "#5ab478" in s.from_ring.styleSheet() and "#5ab478" in s.to_ring.styleSheet()
    from PySide6.QtGui import QColor
    s._set_colour(QColor(200, 40, 40))
    assert "#c82828" in s.from_ring.styleSheet() and "#c82828" in s.to_ring.styleSheet()


def test_a_new_group_border_matches_its_colour_swatch(win):
    s = win.panels["Set Frame Group"]
    s.new_group(3, 3)
    colour = s._colour.name()
    assert colour in s.from_ring.styleSheet() and colour in s.colour_btn.styleSheet()
