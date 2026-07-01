"""Ren'Py Translator - Persistent file logging.

The packaged .exe runs windowed (console=False in the .spec), so anything an
unhandled exception would normally print to stderr is otherwise invisible —
the app just silently misbehaves or "does nothing". This module keeps a
rotating log file on disk (independent from the in-app log panel, which is
in-memory only and lost on crash / when the user clicks "Clear logs") so
there is always something to look at after an error.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

APP_DIR_NAME = "RenPyTranslator"
LOG_FILE_NAME = "renpy_translator.log"

_logger: logging.Logger | None = None


def get_log_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    d = Path(base) / APP_DIR_NAME / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_log_file() -> Path:
    return get_log_dir() / LOG_FILE_NAME


def get_logger() -> logging.Logger:
    """Returns the app-wide logger, creating the rotating file handler on first use."""
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("renpy_translator")
    logger.setLevel(logging.INFO)

    handler = logging.handlers.RotatingFileHandler(
        get_log_file(), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(handler)
    logger.propagate = False

    logger.info("=== RenPyTranslator session started ===")
    _logger = logger
    return logger


def install_excepthook() -> None:
    """Route uncaught exceptions to the log file instead of letting them vanish."""
    logger = get_logger()
    previous_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "Unexpected error",
                    "An unexpected error occurred.\n\n"
                    f"Details were saved to:\n{get_log_file()}",
                )
        except Exception:
            pass

        previous_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook
