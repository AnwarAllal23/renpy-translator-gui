"""Ren'Py Translator - Application entrypoint.

This module is intentionally small: it only bootstraps the Qt application,
creates the main window, and starts the event loop.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from app.main_window import MainWindow
from app.theme import qss_dark
from app.version import APP_DISPLAY_VERSION
from core.log_setup import install_excepthook


def _create_splash() -> QSplashScreen:
    """Create the startup loading screen shown before the main window exists."""
    pixmap = QPixmap(520, 280)
    pixmap.fill(QColor("#0f172a"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor("#38bdf8"))
    painter.setFont(QFont("Arial", 24, QFont.Bold))
    painter.drawText(36, 82, "Ren'Py Translator")
    painter.setPen(QColor("#dbeafe"))
    painter.setFont(QFont("Arial", 12))
    painter.drawText(38, 116, APP_DISPLAY_VERSION)
    painter.setPen(QColor("#64748b"))
    painter.drawLine(38, 148, 482, 148)
    painter.setPen(QColor("#94a3b8"))
    painter.drawText(38, 210, "Preparing translation workspace...")
    painter.end()

    splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
    splash.setWindowFlag(Qt.FramelessWindowHint)
    return splash


def _show_loading_step(app: QApplication, splash: QSplashScreen, message: str) -> None:
    """Update the splash text and keep the UI responsive during startup."""
    splash.showMessage(message, Qt.AlignBottom | Qt.AlignHCenter, QColor("#e2e8f0"))
    app.processEvents()
    QThread.msleep(220)


def main() -> int:
    """Create the Qt application, show the main window, and start the event loop."""
    install_excepthook()

    app = QApplication(sys.argv)
    app.setStyleSheet(qss_dark())

    splash = _create_splash()
    splash.show()
    _show_loading_step(app, splash, "Loading settings...")

    game_dir = None
    if len(sys.argv) > 1:
        p = Path(sys.argv[1]).expanduser().resolve()
        if p.exists():
            game_dir = p

    _show_loading_step(app, splash, "Building interface...")
    w = MainWindow(initial_project=game_dir)
    _show_loading_step(app, splash, "Starting application...")
    w.show()
    splash.finish(w)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
