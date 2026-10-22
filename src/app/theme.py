"""Dark theme (the only look in v1, section 5.2)."""
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

BG = QColor(30, 30, 34)
PANEL = QColor(42, 42, 48)
TEXT = QColor(230, 230, 235)
DISABLED = QColor(120, 120, 128)
ACCENT = QColor(80, 140, 220)
BUTTON = QColor(66, 70, 82)           # lighter than the panels so buttons stand out

# Buttons that can be switched on (Play, the Scale switch): the lit state is a clearly lighter grey with a white border.
TOGGLE_BUTTON_STYLE = (
    "QPushButton { background: #424652; border: 1px solid #7a8094; border-radius: 4px; padding: 0 2px; }"
    "QPushButton:hover { background: #4e5362; }"
    "QPushButton:pressed { background: #5a6072; }"
    "QPushButton:checked { background: #b4bdd6; color: #14151a; border: 1px solid #ffffff; }"
    "QPushButton:disabled { background: #30323a; color: #78787f; border: 1px solid #45474f; }")

SCROLLBAR_STYLE = (
    "QScrollBar:horizontal { background: #1e1f24; height: 14px; border: 1px solid #4a4e5a; border-radius: 4px; margin: 0; }"
    "QScrollBar::handle:horizontal { background: #aab2c8; border-radius: 3px; min-width: 30px; margin: 2px; }"
    "QScrollBar::handle:horizontal:hover { background: #c8cfe0; }"
    "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; height: 0; }"
    "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }")


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.Window, BG)
    p.setColor(QPalette.WindowText, TEXT)
    p.setColor(QPalette.Base, PANEL)
    p.setColor(QPalette.AlternateBase, BG)
    p.setColor(QPalette.Text, TEXT)
    p.setColor(QPalette.Button, BUTTON)
    p.setColor(QPalette.ButtonText, TEXT)
    p.setColor(QPalette.ToolTipBase, PANEL)
    p.setColor(QPalette.ToolTipText, TEXT)
    p.setColor(QPalette.Highlight, ACCENT)
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, DISABLED)
    app.setPalette(p)


def short_popup(combo, rows: int = 10) -> None:
    """A long list (every frame of a project, up to 120) drops down as a scrolling list of `rows` lines,
    not one giant list that runs off the top and bottom of the screen."""
    combo.setMaxVisibleItems(rows)
    combo.setStyleSheet("combobox-popup: 0;")
