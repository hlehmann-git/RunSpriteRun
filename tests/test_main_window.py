import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from src.app.main_window import MainWindow, REGIONS


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_skeleton(app):
    w = MainWindow()
    w.show()
    assert w.minimumSize().width() == 1280 and w.minimumSize().height() == 948
    assert [a.text() for a in w.menuBar().actions()] == ["File", "Edit", "Group", "Help", "About"]
    assert len(w.panels) == len(REGIONS)
    assert not w.act_save.isEnabled() and w.act_new.isEnabled() and w.act_exit.isEnabled()
    w.set_project_active(True)
    assert w.act_open.isEnabled() and w.act_settings.isEnabled() and w.act_help.isEnabled()


def test_palette_and_colour_editor_are_one_card(app):
    """Version 1.b: the colour editor sits directly under the palette; the card grows with the slot count."""
    w = MainWindow()
    w.show()
    pal, ed = w.panels["Palette panel"], w.panels["Colour editor"]
    heights = {}
    for slots in (16, 32, 64):
        pal.grid.set_state([], slots, None)
        pal.height_changed.emit(pal.wanted_height())
        assert ed.geometry().top() == pal.geometry().bottom() + 1
        assert pal.geometry().left() == ed.geometry().left() and pal.width() == ed.width() == 336
        heights[slots] = pal.height()
    assert heights[16] < heights[32] < heights[64]
    assert ed.geometry().bottom() < w.panels["Timeline and frames"].geometry().top()   # 64 slots still fit above the timeline


def test_keys_slot_holds_the_working_edit_panel(app):
    w = MainWindow()
    panel = w.panels["Keys"]
    assert panel.width() == 688 and panel.body.width() == 686
    assert panel.edit_btn.text() == "Edit mode" and panel.v1_btn.isChecked() and not panel.work.isEnabled()
