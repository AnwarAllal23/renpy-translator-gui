"""Application identity and release metadata.

Keeping the product name and version in one small module avoids hard-coded
release strings drifting between the UI, splash screen, documentation, and
packaging scripts.
"""

from __future__ import annotations


APP_NAME = "Ren'Py Translator"
APP_EDITION = "Pro"
APP_VERSION = "0.3.0"
APP_DISPLAY_NAME = f"{APP_NAME} - {APP_EDITION}"
APP_DISPLAY_VERSION = f"{APP_DISPLAY_NAME} v{APP_VERSION}"
