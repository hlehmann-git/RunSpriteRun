"""Small helpers shared by several panels."""
from __future__ import annotations


def frame_choice_text(index: int, label: str) -> str:
    """How a frame is listed in a drop-down: its number and label (FR-3.11)."""
    return f"Frame {index + 1} - {label}"


from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QComboBox, QSlider


class WheelGuard(QObject):
    """Stops the mouse wheel changing a drop-down, spin box or slider unless it
    has been clicked into first. The wheel scrolls whatever is behind it."""

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Wheel
                and isinstance(obj, (QComboBox, QAbstractSpinBox, QSlider))
                and not obj.hasFocus()):
            parent = obj.parentWidget()
            if parent is not None:
                QApplication.sendEvent(parent, event)
            else:
                event.ignore()
            return True
        return False


_guard: WheelGuard | None = None


def install_wheel_guard() -> WheelGuard:
    """Install once for the whole application."""
    global _guard
    app = QApplication.instance()
    if _guard is None:
        _guard = WheelGuard(app)
        app.installEventFilter(_guard)
    return _guard
