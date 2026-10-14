import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from src.app.edit_flow import EditStartDialog


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_default_and_sub_options_are_all_radios(app):
    d = EditStartDialog(None, 3)
    assert d.existing.isChecked() and not d.new.isChecked()
    assert not any(w.isEnabled() for w in d.options)                    # greyed until Create new frame is picked
    assert d.choice() == {"new": False, "where": "after", "copy": False}
    d.new.setChecked(True)
    assert all(w.isEnabled() for w in d.options) and d.empty_after.isChecked()


def test_picking_a_sub_option_keeps_create_new_frame_selected(app):
    d = EditStartDialog(None, 3)
    d.new.setChecked(True)
    expected = {d.copy_before: ("before", True), d.copy_after: ("after", True), d.copy_first: ("first", True),
                d.empty_before: ("before", False), d.empty_after: ("after", False), d.empty_first: ("first", False)}
    for radio, (where, copy) in expected.items():
        radio.setChecked(True)
        assert d.new.isChecked() and all(w.isEnabled() for w in d.options)
        assert [w for w in d.options if w.isChecked()] == [radio]        # exactly one of the six
        assert d.choice() == {"new": True, "where": where, "copy": copy}
    d.existing.setChecked(True)
    assert not d.new.isChecked() and d.choice()["new"] is False
