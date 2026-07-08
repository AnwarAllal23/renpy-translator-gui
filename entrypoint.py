"""Ren'Py Translator - Application entrypoint.

This module is intentionally small: it only bootstraps the Qt application,
creates the main window, and starts the event loop.
"""

import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.theme import qss_dark
from core.log_setup import install_excepthook


def main() -> int:
    """Create the Qt application, show the main window, and start the event loop."""
    install_excepthook()

    app = QApplication(sys.argv)
    app.setStyleSheet(qss_dark())

    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
