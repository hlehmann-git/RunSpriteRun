"""Edit > Shrink Sprite: core logic, dialog and menu."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.app import messages, shrink_dialog
from src.app.main_window import MainWindow
from src.core.project import Frame, Project
from src.core.shrink import SHRINK_PERCENTS, can_shrink, new_size, shrink_project
from src.core.systems import get_system


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def make(w=16, h=16, n=3):
    frames = []
    for i in range(n):
        im = Image.new("RGB", (w, h), (0, 0, 0))
        im.paste((255, 0, 0), (0, 0, w // 2, h))
        frames.append(Frame(f"f_{i + 1:03d}", im))
    return Project("P", get_system("Atari ST"), w, h, transparent=(0, 0, 0), frames=frames, dirty=False)


def test_sizes_round_half_up():
    assert new_size(16, 16, 50) == (8, 8)
    assert new_size(15, 15, 50) == (8, 8)
    assert new_size(16, 16, 87.5) == (14, 14)
    assert new_size(9, 9, 12.5) == (1, 1)


def test_too_small_refused():
    assert not can_shrink(16, 16, 12.5)
    assert can_shrink(16, 16, 25)
    p = make()
    with pytest.raises(ValueError):
        shrink_project(p, 12.5)


def test_shrink_keeps_palette_and_marks_dirty():
    p = make()
    shrink_project(p, 50)
    assert (p.width, p.height) == (8, 8) and p.dirty
    for f in p.frames:
        assert f.image.size == (8, 8)
        assert {c for _, c in f.image.convert("RGB").getcolors()} <= {(0, 0, 0), (255, 0, 0)}


def test_percent_list():
    assert SHRINK_PERCENTS == (87.5, 75, 50, 25, 12.5)


def test_dialog_new_size_and_ok(app):
    d = shrink_dialog.ShrinkDialog(None, 16, 16)
    assert d.new.text() == "8 x 8 pixels"
    d.size_box.setCurrentIndex(d.size_box.findData(12.5))
    assert not d.ok.isEnabled() and d.problem.text()
    d.size_box.setCurrentIndex(d.size_box.findData(25))
    assert d.ok.isEnabled() and d.new.text() == "4 x 4 pixels"


def test_menu_flow(app, monkeypatch):
    w = MainWindow()
    assert not w.act_shrink.isEnabled()
    w.set_project(make())
    assert w.act_shrink.isEnabled()
    w.controller.edit.mode = True
    w._update_edit_actions()
    assert not w.act_shrink.isEnabled()
    w.controller.edit.mode = False
    w._update_edit_actions()
    p = w.controller.project
    monkeypatch.setattr(shrink_dialog.ShrinkDialog, "exec", lambda self: True)
    monkeypatch.setattr(messages, "choose", lambda *a, **k: False)
    w.shrink_sprite()
    assert w.controller.project.width == 16                  # Cancel at the second question changes nothing
    monkeypatch.setattr(messages, "choose", lambda *a, **k: True)
    w.shrink_sprite()
    p = w.controller.project
    assert (p.width, p.height) == (8, 8) and p.dirty
    assert not w.controller.can_undo
