"""RunSpriteRun entry point."""
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.app.main_window import MainWindow
from src.app.theme import apply_dark_theme
from src.io import paths


def main() -> int:
    # Pass-through scaling keeps 125% display scaling exact (section 6.3).
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    paths.projects_folder()                     # make sure the Projects folder exists
    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    # Cancel in the Start Project dialog at launch quits the app (section 5.3).
    if not window.show_start_project():
        return 0
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
