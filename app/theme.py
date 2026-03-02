# app/theme.py
from __future__ import annotations

def qss_dark() -> str:
    """Dark theme QSS matching the website palette (Slate + Blue + Pink)."""
    bg = "#0f172a"
    bg_light = "#1e293b"
    bg_lighter = "#334155"
    primary = "#3b82f6"
    primary_hover = "#2563eb"
    accent = "#ec4899"
    accent_hover = "#db2777"
    text = "#f8fafc"
    text_secondary = "#94a3b8"
    border = "#475569"

    return f"""
    * {{
        font-family: Inter, "Segoe UI", Arial;
        color: {text};
    }}

    QMainWindow, QWidget {{
        background: {bg};
    }}

    /* -------- Top bar (menu + window buttons) -------- */
    QWidget#TopBar {{
        background: rgba(30, 41, 59, 0.75);
        border-bottom: 1px solid {border};
    }}

    QMenuBar#TopMenuBar {{
        background: transparent;
    }}
    QMenuBar::item {{
        padding: 8px 10px;
        background: transparent;
        color: {text_secondary};
        border-radius: 8px;
    }}
    QMenuBar::item:selected {{
        color: {text};
        background: {bg_lighter};
    }}

    /* Menu popup */
    QMenu {{
        background: {bg_light};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 8px 14px;
        color: {text_secondary};
        border-radius: 8px;
    }}
    QMenu::item:selected {{
        background: rgba(236, 72, 153, 0.18);
        color: {text};
    }}

    /* 3 dots window buttons */
    QToolButton#WinBtnMin, QToolButton#WinBtnMax, QToolButton#WinBtnClose {{
        width: 14px;
        height: 14px;
        border-radius: 7px;
        border: 1px solid rgba(0,0,0,0.25);
    }}
    QToolButton#WinBtnClose {{ background: #ff5f57; }}
    QToolButton#WinBtnMax   {{ background: #28c840; }}
    QToolButton#WinBtnMin   {{ background: #febc2e; }}
    QToolButton#WinBtnClose:hover,
    QToolButton#WinBtnMax:hover,
    QToolButton#WinBtnMin:hover {{
        border: 1px solid rgba(255,255,255,0.35);
    }}

    /* -------- Group boxes -------- */
    QGroupBox {{
        border: 1px solid {border};
        border-radius: 12px;
        margin-top: 10px;
        background: {bg_light};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 6px;
        color: {text};
    }}

    /* -------- Inputs -------- */
    QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
        background: {bg_light};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 8px 10px;
        selection-background-color: {primary};
        selection-color: white;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border: 1px solid {primary};
    }}

    /* -------- Buttons -------- */
    QPushButton {{
        background: {bg_light};
        border: 1px solid {border};
        border-radius: 12px;
        padding: 10px 14px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {bg_lighter};
        border-color: {primary};
    }}
    QPushButton:pressed {{
        background: {bg_lighter};
        border-color: {accent};
    }}

    QPushButton#btnPrimary {{
        background: {primary};
        border-color: {primary};
        color: white;
    }}
    QPushButton#btnPrimary:hover {{
        background: {primary_hover};
    }}

    QPushButton#btnAccent {{
        background: {accent};
        border-color: {accent};
        color: white;
    }}
    QPushButton#btnAccent:hover {{
        background: {accent_hover};
    }}

    /* -------- Lists / Tables -------- */
    QListWidget, QTableWidget {{
        background: {bg_light};
        border: 1px solid {border};
        border-radius: 12px;
        gridline-color: {border};
    }}
    QHeaderView::section {{
        background: {bg_lighter};
        color: {text};
        border: 0px;
        padding: 8px;
        font-weight: 700;
    }}

    /* -------- Progress -------- */
    QProgressBar {{
        background: {bg_light};
        border: 1px solid {border};
        border-radius: 10px;
        text-align: center;
        height: 16px;
    }}
    QProgressBar::chunk {{
        background: {primary};
        border-radius: 10px;
    }}
    """