# app/theme.py
from __future__ import annotations

def qss_dark() -> str:
    """Dark theme QSS - deep indigo canvas, glass cards, blue -> violet -> pink accents."""
    bg = "#0a0e1a"
    bg_soft = "#0d1224"
    bg_light = "#131a2e"
    bg_lighter = "#1c2540"
    bg_hover = "#232d4d"
    primary = "#3b82f6"
    primary2 = "#6366f1"
    primary_hover = "#2563eb"
    accent = "#ec4899"
    accent2 = "#f43f5e"
    accent_hover = "#db2777"
    success = "#22c55e"
    danger = "#ef4444"
    text = "#f1f5f9"
    text_secondary = "#8b96b3"
    text_muted = "#5b6485"
    border = "#232d4d"
    border_soft = "#1a2138"

    return f"""
    * {{
        font-family: "Segoe UI", Inter, Arial;
        color: {text};
    }}

    QMainWindow, QWidget {{
        background: {bg};
    }}

    QToolTip {{
        background: {bg_lighter};
        color: {text};
        border: 1px solid {primary};
        border-radius: 6px;
        padding: 4px 8px;
    }}

    /* -------- Top bar (menu + window buttons) -------- */
    QWidget#TopBar {{
        background: {bg_soft};
        border-bottom: 1px solid {border_soft};
    }}

    QLabel#LogoChip {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {primary}, stop:0.55 {primary2}, stop:1 {accent});
        border-radius: 9px;
        font-size: 12px;
    }}

    QLabel#BrandLabel {{
        font-weight: 700;
        font-size: 13px;
        color: {text};
        padding-right: 2px;
    }}

    QLabel#ProBadge {{
        background: rgba(236, 72, 153, 0.16);
        color: {accent};
        border: 1px solid rgba(236, 72, 153, 0.45);
        border-radius: 7px;
        font-size: 9px;
        font-weight: 700;
        padding: 1px 6px;
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
        background: {bg_hover};
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
        background: rgba(99, 102, 241, 0.22);
        color: {text};
    }}
    QMenu::separator {{
        height: 1px;
        background: {border};
        margin: 6px 4px;
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
        border: 1px solid rgba(255,255,255,0.45);
    }}

    /* -------- Group boxes (cards) -------- */
    QGroupBox {{
        border: 1px solid {border};
        border-radius: 14px;
        margin-top: 16px;
        padding-top: 8px;
        background: {bg_light};
        font-weight: 700;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 2px 8px;
        color: {text};
        font-weight: 700;
        font-size: 12px;
    }}

    QGroupBox#CardActions {{
        border: 1px solid rgba(236, 72, 153, 0.35);
    }}

    QLabel#ProjectPathLabel {{
        color: {text_secondary};
        font-weight: 400;
    }}

    QLabel#LangArrow {{
        color: {primary};
        font-weight: 700;
        font-size: 16px;
        padding: 0 4px;
    }}

    QLabel#SectionCaption {{
        color: {text_muted};
        font-weight: 700;
        font-size: 10px;
        letter-spacing: 1px;
    }}

    /* -------- Status pill -------- */
    QLabel#StatusPill {{
        border-radius: 11px;
        padding: 4px 14px;
        font-weight: 700;
        font-size: 11px;
        background: rgba(139, 150, 179, 0.14);
        color: {text_secondary};
        border: 1px solid rgba(139, 150, 179, 0.30);
    }}
    QLabel#StatusPill[state="busy"] {{
        background: rgba(59, 130, 246, 0.16);
        color: #93c5fd;
        border: 1px solid rgba(59, 130, 246, 0.45);
    }}
    QLabel#StatusPill[state="success"] {{
        background: rgba(34, 197, 94, 0.16);
        color: #86efac;
        border: 1px solid rgba(34, 197, 94, 0.45);
    }}
    QLabel#StatusPill[state="error"] {{
        background: rgba(239, 68, 68, 0.16);
        color: #fca5a5;
        border: 1px solid rgba(239, 68, 68, 0.45);
    }}

    /* -------- Inputs -------- */
    QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
        background: {bg_lighter};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 8px 10px;
        selection-background-color: {primary};
        selection-color: white;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border: 1px solid {primary};
    }}
    QLineEdit:disabled, QComboBox:disabled {{
        color: {text_muted};
    }}

    /* -------- Buttons -------- */
    QPushButton {{
        background: {bg_lighter};
        border: 1px solid {border};
        border-radius: 12px;
        padding: 10px 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {bg_hover};
        border-color: {primary};
    }}
    QPushButton:pressed {{
        background: {bg_light};
        border-color: {accent};
    }}
    QPushButton:disabled {{
        background: {bg_light};
        border-color: {border_soft};
        color: {text_muted};
    }}

    QPushButton#btnPrimary {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {primary}, stop:1 {primary2});
        border: 1px solid {primary2};
        color: white;
    }}
    QPushButton#btnPrimary:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {primary_hover}, stop:1 {primary2});
    }}
    QPushButton#btnPrimary:disabled {{
        background: {bg_light};
        border-color: {border_soft};
        color: {text_muted};
    }}

    QPushButton#btnAccent {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {accent}, stop:1 {accent2});
        border: 1px solid {accent2};
        color: white;
    }}
    QPushButton#btnAccent:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {accent_hover}, stop:1 {accent2});
    }}
    QPushButton#btnAccent:disabled {{
        background: {bg_light};
        border-color: {border_soft};
        color: {text_muted};
    }}

    /* -------- Lists / Tables / Tree -------- */
    QListWidget, QTableWidget, QTreeWidget {{
        background: {bg_soft};
        border: 1px solid {border};
        border-radius: 12px;
        gridline-color: {border};
        outline: 0;
    }}
    QListWidget::item, QTreeWidget::item {{
        padding: 5px 2px;
        border-radius: 6px;
    }}
    QTreeWidget::item {{
        height: 22px;
    }}
    QListWidget::item:hover, QTreeWidget::item:hover,
    QTableWidget::item:hover {{
        background: {bg_hover};
    }}
    QListWidget::item:selected, QTreeWidget::item:selected,
    QTableWidget::item:selected {{
        background: rgba(99, 102, 241, 0.30);
        color: {text};
    }}
    QHeaderView::section {{
        background: {bg_lighter};
        color: {text_secondary};
        border: 0px;
        border-bottom: 1px solid {border};
        padding: 8px;
        font-weight: 700;
    }}
    QTreeWidget::branch {{
        background: transparent;
    }}

    /* -------- Splitter -------- */
    QSplitter::handle {{
        background: transparent;
    }}
    QSplitter::handle:horizontal {{
        width: 6px;
        margin: 4px 0;
    }}
    QSplitter::handle:hover {{
        background: rgba(99, 102, 241, 0.35);
        border-radius: 3px;
    }}

    /* -------- Combo box popup -------- */
    QComboBox::drop-down {{
        border: 0px;
        width: 26px;
    }}
    QComboBox QAbstractItemView {{
        background: {bg_lighter};
        border: 1px solid {border};
        border-radius: 8px;
        selection-background-color: {primary};
        selection-color: white;
        outline: 0;
        padding: 4px;
    }}

    /* -------- Scrollbars -------- */
    QScrollBar:vertical {{
        background: transparent;
        width: 12px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {bg_hover};
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {primary2};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 12px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {bg_hover};
        border-radius: 5px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {primary2};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    /* -------- Status bar -------- */
    QStatusBar {{
        color: {text_secondary};
        background: {bg_soft};
        border-top: 1px solid {border_soft};
    }}

    /* -------- Progress -------- */
    QProgressBar {{
        background: {bg_lighter};
        border: 1px solid {border};
        border-radius: 9px;
        text-align: center;
        height: 16px;
        color: {text_secondary};
        font-weight: 700;
        font-size: 10px;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {primary}, stop:0.6 {primary2}, stop:1 {accent});
        border-radius: 9px;
    }}

    /* -------- Dialogs -------- */
    QDialog {{
        background: {bg};
    }}

    QMessageBox {{
        background: {bg_light};
    }}

    /* -------- Log console -------- */
    QTextEdit#LogConsole {{
        background: {bg_soft};
        border: 1px solid {border};
        border-radius: 12px;
        selection-background-color: {primary2};
        selection-color: white;
    }}
    """
