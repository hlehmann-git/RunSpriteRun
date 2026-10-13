import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from src.app.main_window import MainWindow
from src.core.project import Frame, Group, Project, Rule
from src.core.systems import get_system


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def make_project(w=16, h=16):
    frames = [Frame(f"f{i + 1}", Image.new("RGB", (w, h), (73 * (i % 3), 0, 0))) for i in range(12)]
    groups = [Group("Walk", 0, 2, key="D", on_release=Rule("frame", "f10")),
              Group("Jump", 4, 6, key="W", on_release=Rule("group", "Walk", False))]
    return Project("P", get_system("Atari ST"), w, h, fps=24, frames=frames, groups=groups, dirty=False)


@pytest.fixture
def win(app):
    w = MainWindow()
    w.show()
    w.activateWindow()
    w.set_project(make_project())
    app.processEvents()
    return w


def key(win, qt_key, down=True, auto=False, mods=Qt.NoModifier):
    ev = QKeyEvent(QEvent.KeyPress if down else QEvent.KeyRelease, qt_key, mods, "", auto)
    QApplication.sendEvent(win, ev)


def test_f5_toggles_and_the_idle_window_shows_the_start_state(win):
    c = win.controller
    run = win.panels["RunSpriteRun window"]
    assert not c.running and c.runner.frame == 0
    win.f5.activated.emit()
    assert c.running and c.timer.isActive()
    win.f5.activated.emit()
    assert not c.running and not c.timer.isActive()


def test_key_with_a_group_starts_running_then_loops_and_highlights(win):
    c = win.controller
    pad = win.panels["Timeline and frames"].pad
    key(win, Qt.Key_A)                                        # no group on A: nothing starts
    assert not c.running and pad.held == set()
    key(win, Qt.Key_A, down=False)
    key(win, Qt.Key_D)                                        # D has a group: starts as F5 does and plays it
    assert c.running and c.timer.isActive()
    assert pad.held == {"D"} and c.runner.playing_group == "Walk"
    c._tick()
    assert c.runner.frame == 1
    key(win, Qt.Key_D, auto=True)                             # auto-repeat ignored
    assert c.runner.frame == 1
    key(win, Qt.Key_D, down=False)
    assert pad.held == set() and c.runner.frame == 9 and c.running   # resting state: Go To Frame f10; still running


def test_f5_or_the_button_stops_a_key_started_run(win):
    c = win.controller
    key(win, Qt.Key_W)
    assert c.running
    win.f5.activated.emit()
    assert not c.running and not c.timer.isActive() and c.runner.held == []
    key(win, Qt.Key_W, down=False)                            # releasing afterwards does nothing
    assert not c.running
    key(win, Qt.Key_D)
    assert c.running
    win.panels["RunSpriteRun window"].f5_btn.click()
    assert not c.running


def test_auto_start_needs_no_text_focus_and_no_modifiers(win):
    c = win.controller
    key(win, Qt.Key_D, mods=Qt.ControlModifier)
    assert not c.running
    win.panels["Timeline and frames"].slots[0].label.setFocus()
    QApplication.processEvents()
    if QApplication.focusWidget() is win.panels["Timeline and frames"].slots[0].label:
        key(win, Qt.Key_D)
        assert not c.running


def test_timeline_marks_the_running_frame_and_clears_on_stop(win):
    tl = win.panels["Timeline and frames"]
    win.toggle_run()
    key(win, Qt.Key_W)
    assert tl.slots[4 - tl.first].thumb.playing
    win.toggle_run()
    assert not tl.slots[4 - tl.first].thumb.playing           # (the preview may still mark frames 1 to 3)


def test_keypad_digits_and_modifiers(win):
    c = win.controller
    c.project.groups[0].key = "3"
    win.toggle_run()
    key(win, Qt.Key_3, mods=Qt.KeypadModifier)                # numeric keypad
    assert "3" in c.runner.held
    key(win, Qt.Key_3, down=False, mods=Qt.KeypadModifier)
    key(win, Qt.Key_W, mods=Qt.ControlModifier)               # Ctrl+W is not a RunSpriteRun key
    assert c.runner.held == []


def test_keys_ignored_while_a_text_box_has_focus(win):
    tl = win.panels["Timeline and frames"]
    win.toggle_run()
    win.toggle_run()
    tl.slots[0].label.setFocus()
    QApplication.processEvents()
    if QApplication.focusWidget() is tl.slots[0].label:
        win.toggle_run()
        # starting RunSpriteRun takes focus out of the text box so the keys work
        assert QApplication.focusWidget() is not tl.slots[0].label


def test_editing_groups_stops_running(win):
    c = win.controller
    win.toggle_run()
    key(win, Qt.Key_D)
    c.frames_changed.emit()
    assert not c.running and c.runner.held == [] and win.panels["Timeline and frames"].pad.held == set()


def test_scale_and_zoom(win):
    run = win.panels["RunSpriteRun window"]
    assert run.max_zoom == 16 and run.zoom == 16 and run.switch.isChecked()    # 16 x 16 fits at 16x
    assert not run.plus.isEnabled() and run.minus.isEnabled()
    run.minus.click()
    assert run.zoom == 15 and not run.switch.isChecked() and run.plus.isEnabled()
    run.switch.click()                                          # toggle jumps to the largest zoom
    assert run.zoom == 16
    run.switch.click()                                          # and back to actual size
    assert run.zoom == 1 and not run.minus.isEnabled() and run.view.zoom == 1


def test_non_square_sprite_zoom_limit(app):
    w = MainWindow()
    w.show()
    w.set_project(make_project(14, 48))
    run = w.panels["RunSpriteRun window"]
    assert run.max_zoom == 5                                    # 256 // 48 = 5 (PRD example)


def test_rendering_at_zoom_is_whole_number_and_centred():
    from src.app.render import render_sprite_at
    img = Image.new("RGB", (4, 4), (200, 0, 0))
    out = render_sprite_at(img, (0, 0, 255), 32, 32, 3)
    assert out.size == (32, 32) and out.getpixel((16, 16)) == (200, 0, 0)
    assert out.getpixel((9, 16)) == (0, 0, 0) and out.getpixel((10, 16)) == (200, 0, 0)   # 12 px wide, from x=10
    assert out.getpixel((21, 16)) == (200, 0, 0) and out.getpixel((22, 16)) == (0, 0, 0)


def test_f5_toggle_button_does_what_f5_does(win):
    run = win.panels["RunSpriteRun window"]
    c = win.controller
    assert not c.running and not run.f5_btn.isChecked()
    run.f5_btn.click()
    assert c.running and run.f5_btn.isChecked()
    win.f5.activated.emit()                                    # the real F5 keeps the button in step
    assert not c.running and not run.f5_btn.isChecked()
    run.f5_btn.click()
    run.f5_btn.click()
    assert not c.running and not run.f5_btn.isChecked()


def test_idle_window_follows_selection_and_running_does_not(win):
    c = win.controller
    run = win.panels["RunSpriteRun window"]
    p = c.project
    c.select(7)
    assert run.view._image is p.frames[7].image
    win.toggle_run()                                           # start state: Go To Frame 1
    assert run.view._image is p.frames[0].image
    c.select(8)                                                # not while running
    assert run.view._image is p.frames[0].image
    win.toggle_run()
    assert run.view._image is p.frames[0].image                # stopping returns to the start state
    c.select(9)
    assert run.view._image is p.frames[9].image
