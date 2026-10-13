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


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def log(monkeypatch):
    out = {"choose": [], "answer": True}
    monkeypatch.setattr(messages, "warn", lambda p, t, d=None: None)
    monkeypatch.setattr(messages, "info", lambda p, t, d=None: None)
    monkeypatch.setattr(messages, "choose", lambda p, t, d, y, n: (out["choose"].append(t), out["answer"])[1])
    return out


def make():
    a, b = (0, 0, 0), (lv(7, 3), 0, 0)
    f1 = Image.new("RGB", (8, 8), a)
    f1.putpixel((2, 3), b)
    f2 = Image.new("RGB", (8, 8), b)
    return Project("P", get_system("Atari ST"), 8, 8, frames=[Frame("f1", f1), Frame("f2", f2)],
                   groups=[Group("G", 0, 1)], dirty=False)


@pytest.fixture
def win(app, log):
    w = MainWindow()
    w.show()
    w.set_project(make())
    return w


def ed(w):
    return w.panels["Colour editor"]


def pal(w):
    return w.panels["Palette panel"]


def click_slot(w, i):
    g = pal(w).grid
    QTest.mouseClick(g, Qt.LeftButton, Qt.NoModifier, g.slot_rect(i).center())


def test_starts_with_first_palette_colour_disarmed(win):
    e = ed(win)
    assert e.colour == (0, 0, 0) and not e.armed
    assert e.hex.text() == "#000000"
    assert [s.maximum() for s in e.sliders] == [7, 7, 7]


def test_square_click_sets_preview_and_arms(win):
    e = ed(win)
    QTest.mouseClick(e.square, Qt.LeftButton, Qt.NoModifier, QPoint(31, 0))
    assert e.colour == (255, 0, 0) and e.armed
    assert [s.value() for s in e.sliders] == [7, 0, 0]
    assert e.hex.text() == "#FF0000"


def test_overwrite_palette_square_then_disarm(win):
    e = ed(win)
    p = win.controller.project
    e.sliders[2].setValue(7)                                   # blue 7: (0,0,255)
    assert e.armed
    click_slot(win, 0)
    assert p.frames[0].image.getpixel((0, 0)) == (0, 0, 255)
    assert p.transparent == (0, 0, 255)                        # first colour was the transparent one
    assert not e.armed and e.colour == (0, 0, 255)             # preview stays, disarmed
    click_slot(win, 1)                                         # nothing armed: nothing changes
    assert p.frames[1].image.getpixel((0, 0)) == (lv(7, 3), 0, 0)


def test_free_slot_click_ignored(win):
    e = ed(win)
    e.sliders[1].setValue(3)
    click_slot(win, 9)
    assert e.armed and win.controller.project.frames[0].image.getpixel((0, 0)) == (0, 0, 0)


def test_hex_box(win):
    e = ed(win)
    e.hex.setText("12ab34")                                    # no '#'
    e.hex.editingFinished.emit()
    assert e.colour == (0, lv(5, 3), lv(1, 3)) and e.armed          # snapped to the system
    assert e.hex.text() == "#{:02X}{:02X}{:02X}".format(*e.colour)
    e.hex.setText("zzz")
    e.hex.editingFinished.emit()
    assert e.hex.text() == "#{:02X}{:02X}{:02X}".format(*e.colour)       # invalid: back to the current colour


def test_merge_asks_and_frees_slot(win, log):
    e = ed(win)
    p = win.controller.project
    e.sliders[0].setValue(7)                                   # (255,0,0) is already slot 2
    log["answer"] = False
    click_slot(win, 0)
    assert log["choose"] == ["Merge these colours?"] and len(p.palette()) == 2
    e.sliders[0].setValue(7)
    log["answer"] = True
    click_slot(win, 0)
    assert len(p.palette()) == 1


def test_transparent_box(win):
    e = ed(win)
    p = win.controller.project
    e.t_box.click()
    assert e.transparent_armed
    click_slot(win, 1)
    assert p.transparent == (lv(7, 3), 0, 0) and not e.transparent_armed
    assert e.t_box.colour == p.transparent


def test_eyedropper_from_frame_view_and_palette(win):
    e = ed(win)
    v = win.panels["Frame view"].view
    e.eyedropper.click()
    assert e.eyedropper_armed
    s = v.zoom or v.max_zoom(8, 8)
    ox = (v.physical_size()[0] - 8 * s) // 2
    oy = (v.physical_size()[1] - 8 * s) // 2
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(ox + 2 * s + 1, oy + 3 * s + 1))
    assert e.colour == (lv(7, 3), 0, 0) and e.armed and not e.eyedropper_armed
    e.eyedropper.click()
    click_slot(win, 0)
    assert e.colour == (0, 0, 0)


def test_undo_redo_palette_and_menu(win):
    p = win.controller.project
    assert not win.act_undo.isEnabled() and not win.act_redo.isEnabled()
    e = ed(win)
    e.sliders[2].setValue(7)
    click_slot(win, 0)
    assert win.act_undo.isEnabled() and not win.act_redo.isEnabled()
    win.act_undo.trigger()
    assert p.frames[0].image.getpixel((0, 0)) == (0, 0, 0) and p.transparent == (0, 0, 0)
    assert win.act_redo.isEnabled() and not win.act_undo.isEnabled()
    win.act_redo.trigger()
    assert p.frames[0].image.getpixel((0, 0)) == (0, 0, 255)


def test_undo_covers_label_move_group_and_clears_on_new_project(win):
    c = win.controller
    p = c.project
    c.rename(0, "walk")
    c.move_frame(0, 1)
    assert [f.label for f in p.frames] == ["f2", "walk"]
    c.undo()
    assert [f.label for f in p.frames] == ["walk", "f2"]
    c.undo()
    assert p.frames[0].label == "f1"
    c.redo()
    assert p.frames[0].label == "walk"
    c.delete_group("G")
    assert p.groups == []
    c.undo()
    assert [g.name for g in p.groups] == ["G"]
    c.set_project(make())
    assert not c.can_undo and not c.can_redo


def test_group_apply_is_one_undo_step(win):
    sg = win.panels["Set Frame Group"]
    sg.name.setText("Renamed")
    assert sg.apply()
    c = win.controller
    assert c.project.groups[0].name == "Renamed"
    c.undo()
    assert c.project.groups[0].name == "G"


def test_edit_steps_limited_to_50(win):
    c = win.controller
    for i in range(60):
        c.rename(0, f"a{i}")
    n = 0
    while c.undo():
        n += 1
    assert n == 50


def test_step_buttons_move_slider_one_level(win):
    e = ed(win)
    e.plus_btns[1].click()
    assert e.sliders[1].value() == 1 and e.armed and e.colour == (0, lv(1, 3), 0)
    e.plus_btns[1].click()
    e.minus_btns[1].click()
    assert e.sliders[1].value() == 1
    e.minus_btns[0].click()                                    # already at 0: stays
    assert e.sliders[0].value() == 0
    for _ in range(10):
        e.plus_btns[2].click()
    assert e.sliders[2].value() == 7 and e.hex.text() == "#{:02X}{:02X}{:02X}".format(*e.colour)


def test_play_and_f5_buttons_light_up(win):
    gp = win.panels["Frame Group Preview"]
    assert not gp.play_btn.isChecked()
    gp.play()
    assert gp.play_btn.isChecked()
    gp.stop()
    assert not gp.play_btn.isChecked()
    win.toggle_run()
    assert win.panels["RunSpriteRun window"].f5_btn.isChecked()
