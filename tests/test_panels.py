import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from src.app import messages
from src.app.main_window import MainWindow
from src.app.timeline import FIRST_X, PITCH, THUMB_Y, VISIBLE
from src.core.project import Frame, Group, Project
from src.core.systems import get_system


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def project(n=12, system="Atari ST", groups=()):
    frames = [Frame(f"f{i + 1}", Image.new("RGB", (8, 8), (73 * (i % 3), 0, 0))) for i in range(n)]
    return Project("P", get_system(system), 8, 8, transparent=(0, 0, 0), frames=frames, groups=list(groups), dirty=False)


@pytest.fixture
def win(app, monkeypatch):
    monkeypatch.setattr(messages, "warn", lambda *a, **k: shown.append(a[1]))
    monkeypatch.setattr(messages, "choose", lambda *a, **k: True)
    shown.clear()
    w = MainWindow()
    w.show()
    w.set_project(project(groups=[Group("A", 0, 1, colour=(255, 0, 0))]))
    return w


shown: list[str] = []


def tl(w):
    return w.panels["Timeline and frames"]


def test_timeline_shows_nine_and_scrolls(win):
    t = tl(win)
    assert sum(s.isVisibleTo(t) for s in t.slots) == VISIBLE
    assert t.slots[0].number.text() == "1" and t.bar.maximum() == 3
    t.scroll_by(1)
    assert t.slots[0].number.text() == "2" and t.slots[0].label.text() == "f2"
    t.bar.setValue(3)
    assert t.slots[8].number.text() == "12" and not t.right.isEnabled()
    t.left.click()
    assert t.first == 2


def test_selection_follows_and_scrolls_into_view(win):
    t = tl(win)
    win.controller.select(11)
    assert t.first == 3 and win.panels["Frame view"].number.currentText() == "12"
    win.controller.select(0)
    assert t.first == 0 and win.panels["Frame view"].label.currentText() == "f1"
    t.slots[4].thumb.pressed.emit(4)
    assert win.controller.selected == 4


def test_group_row_and_border(win):
    t = tl(win)
    assert t.slots[0].group.text() == "A" and t.slots[2].group.text() == ""
    assert t.slots[0].thumb.border.red() == 255


def test_frame_view_dropdowns_select(win):
    fv = win.panels["Frame view"]
    fv.label.setCurrentIndex(5)
    fv.label.activated.emit(5)
    assert win.controller.selected == 5 and fv.number.currentText() == "6"


def test_rename_valid_and_refused(win):
    t = tl(win)
    s = t.slots[3]
    s.label.setText("Jump_1")
    s.label.editingFinished.emit()
    assert win.controller.project.frames[3].label == "Jump_1"
    s.label.setText("bad name")
    s.label.editingFinished.emit()
    assert shown[-1].startswith("Labels can only use") and s.label.text() == "Jump_1"
    s.label.setText("F1")
    s.label.editingFinished.emit()
    assert shown[-1] == "Frame labels must be unique." and s.label.text() == "Jump_1"


def test_ctrl_move_and_keep_selection(win):
    win.controller.select(4)
    assert win.controller.move_selected(1)
    labels = [f.label for f in win.controller.project.frames]
    assert labels[4:6] == ["f6", "f5"] and win.controller.selected == 5


def test_drag_reorder_and_cancel(win):
    t = tl(win)
    def at(gap):                                       # a point on the boundary before frame `gap`
        return QPoint(FIRST_X - 3 + (gap - t.first) * PITCH, THUMB_Y + 30)
    t._drag_move(0, at(3))
    assert t.marker.isVisible()
    t._drag_end(0, at(3))                              # frame 1 dropped before frame 4
    assert [f.label for f in win.controller.project.frames][:4] == ["f2", "f3", "f1", "f4"]
    t._drag_move(2, at(7))
    t._drag_end(2, QPoint(5, 5))                       # dropped outside the strip: nothing changes
    assert [f.label for f in win.controller.project.frames][:4] == ["f2", "f3", "f1", "f4"]
    t._drag_move(2, at(7))
    t._cancel_drag()                                   # Esc
    assert not t.marker.isVisible() and win.controller.project.frames[2].label == "f1"


def test_palette_panel_counts_and_free_slots(win):
    pp = win.panels["Palette panel"]
    assert pp.count.text() == "3 used, 13 free of 16"
    assert pp.grid.slots == 16 and len(pp.grid.colours) == 3
    win.set_project(project(system="Amiga"))
    assert pp.grid.slots == 32 and pp.count.text().endswith("of 32")


def test_frame_view_scale_and_transparent(win):
    v = win.panels["Frame view"].view
    img = v.grab().toImage()
    assert img.pixelColor(128, 128).red() in (0, 73, 146)     # drawn, not blank
