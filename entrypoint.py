"""Ren'Py Translator - Application entrypoint.

This module is intentionally small: it only bootstraps the Qt application,
creates the main window, and starts the event loop.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from PySide6.QtWidgets import QApplication
from app.theme import qss_dark

def main() -> int:
    """Create the Qt application, show the main window, and start the event loop."""
    app = QApplication(sys.argv)

    app.setStyleSheet(qss_dark())

    game_dir = None
    if len(sys.argv) > 1:
        p = Path(sys.argv[1]).expanduser().resolve()
        if p.exists():
            game_dir = p

    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
