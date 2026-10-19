"""Edit > Reduce Palette: core logic, dialog and menu."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.app import messages, reduce_dialog
from src.app.main_window import MainWindow
from src.core.project import Frame, Project
from src.core.reduce_palette import (can_reduce, colour_count, make_mapping, reduce_project, target_range)
from src.core.systems import get_system

RED, RED2, BLUE, GREEN, YELLOW = (255, 0, 0), (250, 10, 10), (0, 0, 255), (0, 250, 0), (255, 255, 0)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def make(system="Atari ST"):
    im = Image.new("RGB", (8, 8), (0, 0, 0))
    cols = [RED, RED2, BLUE, GREEN, (0, 0, 0)]
    for x in range(8):
        for y in range(8):
            im.putpixel((x, y), cols[(x + y) % 5])
    im.putpixel((3, 3), YELLOW)
    return Project("P", get_system(system), 8, 8, transparent=(0, 0, 0), frames=[Frame("a_001", im)], dirty=False)


def test_counts_and_range():
    p = make()
    assert colour_count(p) == 5 and target_range(p) == (2, 4) and can_reduce(p)


def test_reduce_keeps_main_colours_and_uses_only_existing():
    p = make()
    reduce_project(p, 3)
    used = {c for _, c in p.frames[0].image.getcolors()}
    assert used <= {RED, BLUE, GREEN, (0, 0, 0)} and RED2 not in used and p.dirty
    assert colour_count(p) == 3


def test_distinct_small_colour_survives_over_similar_big_ones():
    m = make_mapping({RED: 50, RED2: 40, YELLOW: 2, BLUE: 30}, 3)
    assert m[YELLOW] == YELLOW and m[RED2] == RED


def test_same_answer_every_time_and_range_checked():
    p = make()
    assert make_mapping({RED: 5, BLUE: 5, GREEN: 5}, 2) == make_mapping({RED: 5, BLUE: 5, GREEN: 5}, 2)
    with pytest.raises(ValueError):
        reduce_project(p, 5)
    with pytest.raises(ValueError):
        reduce_project(p, 1)


def test_layers_are_reduced_and_transparent_kept():
    p = make()
    im = p.frames[0].image
    p.frames[0].layers = (im, Image.new("RGB", (8, 8), (0, 0, 0)), Image.new("RGB", (8, 8), (0, 0, 0)))
    reduce_project(p, 2)
    assert RED2 not in p.palette() and (0, 0, 0) in p.palette()
    assert all(RED2 not in {c for _, c in l.getcolors()} for l in p.frames[0].layers)


def test_dialog_preview(app):
    p = make()
    d = reduce_dialog.ReduceDialog(None, p, 0)
    assert (d.target.minimum(), d.target.maximum()) == (2, 4)
    d.target.setValue(3)
    assert "5 colours now, 3 after" in d.summary.text()
    assert d.from_view.pixmap() is not None and d.to_view.pixmap() is not None


def test_menu_flow(app, monkeypatch):
    w = MainWindow()
    assert not w.act_reduce.isEnabled()
    w.set_project(make())
    assert w.act_reduce.isEnabled()
    w.controller.edit.mode = True
    w._update_edit_actions()
    assert not w.act_reduce.isEnabled()
    w.controller.edit.mode = False
    w._update_edit_actions()
    monkeypatch.setattr(reduce_dialog.ReduceDialog, "exec", lambda self: True)
    monkeypatch.setattr(messages, "choose", lambda *a, **k: False)
    w.reduce_palette()
    assert colour_count(w.controller.project) == 5            # Cancel at the second question changes nothing
    monkeypatch.setattr(messages, "choose", lambda *a, **k: True)
    w.reduce_palette()
    assert colour_count(w.controller.project) == 2 and w.controller.project.dirty
    assert not w.controller.can_undo


def test_greyed_out_for_fixed_palette_system(app):
    w = MainWindow()
    p = make("Commodore 64")
    w.set_project(p)
    assert not w.act_reduce.isEnabled()
