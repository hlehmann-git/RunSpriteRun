"""The mouse wheel must not change drop-downs unless they were clicked into."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QComboBox, QSpinBox, QWidget, QVBoxLayout

from src.app.common import install_wheel_guard

app = QApplication.instance() or QApplication([])


def _wheel(w):
    e = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120),
                    Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    app.sendEvent(w, e)


def _box():
    install_wheel_guard()
    host = QWidget()
    lay = QVBoxLayout(host)
    c = QComboBox(); c.addItems(["a", "b", "c"])
    s = QSpinBox(); s.setRange(0, 9)
    lay.addWidget(c); lay.addWidget(s)
    host.show()
    return host, c, s


def test_wheel_does_not_change_unfocused_combo_or_spin():
    host, c, s = _box()
    host.activateWindow()
    _wheel(c); _wheel(s)
    assert c.currentIndex() == 0 and s.value() == 0


def test_wheel_changes_after_clicking_into_it():
    host, c, s = _box()
    host.activateWindow()
    c.setFocus(); s.setFocus()
    app.processEvents()
    if not s.hasFocus():
        return                      # offscreen platform cannot give focus
    s.setValue(5); s.setFocus(); _wheel(s)
    assert s.value() == 4


def test_rules_window_combos_ignore_the_wheel():
    from tests.test_control_window import make
    from src.app.main_window import MainWindow
    from src.core.project import ControlRule
    w = MainWindow()
    w.show()
    w.set_project(make(rules=[ControlRule(["W", "D"], "TurnLeft", once=True)]))
    w.set_frame_group.rules_btn.click()
    cw = w.control_window
    combos = cw.findChildren(QComboBox)
    assert combos
    before = [c.currentIndex() for c in combos]
    for c in combos:
        c.clearFocus()
        _wheel(c)
    assert [c.currentIndex() for c in combos] == before


def test_a_focused_combo_still_ignores_the_wheel():
    host, c, s = _box()
    host.activateWindow()
    c.setFocus()
    app.processEvents()
    c.setCurrentIndex(1)
    _wheel(c)
    assert c.currentIndex() == 1                       # clicked into, still unchanged
    from PySide6.QtCore import QEvent
    ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    app.sendEvent(c, ev)
    assert c.currentIndex() == 1
