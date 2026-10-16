import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from tests.test_run_ui import app, key, make_project, win  # noqa: F401  (fixtures)


def timeline(win):
    return win.panels["Timeline and frames"]


def test_esc_keeps_typed_label_and_ends_editing(win):
    tl = timeline(win)
    s = tl.slots[0]
    s.label.setFocus()
    QApplication.processEvents()
    assert QApplication.focusWidget() is s.label
    s.label.setText("Hero_1")
    QTest.keyClick(s.label, Qt.Key_Escape)
    assert QApplication.focusWidget() is not s.label
    assert win.controller.project.frames[0].label == "Hero_1_001"


def test_click_outside_keeps_typed_label_and_ends_editing(win):
    tl = timeline(win)
    s = tl.slots[1]
    s.label.setFocus()
    s.label.setText("Hero_2")
    QTest.mouseClick(win.panels["Palette panel"], Qt.LeftButton)
    assert QApplication.focusWidget() is not s.label
    assert win.controller.project.frames[1].label == "Hero_2_002"


def test_click_inside_the_label_keeps_editing(win):
    s = timeline(win).slots[2]
    s.label.setFocus()
    QTest.mouseClick(s.label, Qt.LeftButton)
    assert QApplication.focusWidget() is s.label


def test_no_highlight_when_a_frame_is_held_and_highlight_when_looping(win):
    c = win.controller
    tl = timeline(win)
    win.f5.activated.emit()                       # start state: frame 1 held
    assert c.running and not c.runner.animating and not tl.slots[0].thumb.playing
    key(win, Qt.Key_D)                            # Walk, 3 frames, loops
    assert c.runner.animating
    shown = [s for s in tl.slots if s.thumb.playing]
    assert len(shown) == 1
    key(win, Qt.Key_D, down=False)               # Go To Frame f10: held, nothing animates
    assert not c.runner.animating
    assert not any(s.thumb.playing for s in tl.slots)


def test_key_pad_is_in_the_timeline_and_the_keys_slot_is_empty(win):
    tl = timeline(win)
    keys = win.panels["Keys"]
    assert tl.pad.parent() is tl and tl.pad.width() == 156 and tl.pad.height() == 142
    assert tl.pad.geometry().right() < tl.left.geometry().left()
    assert (keys.width(), keys.height()) == (688, 208)      # 1.b: runs to the right edge of the window
    assert keys.title.isHidden() and not keys.findChildren(type(tl.pad))
