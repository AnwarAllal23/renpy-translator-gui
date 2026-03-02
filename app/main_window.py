"""
Ren'Py Translator - Main Qt window and UI workflow.

This file contains the main application window and the dialogs/workers that
power the translation workflow:
- Selecting a Ren'Py project (source or packaged)
- Preparing a workspace for packaged games (optional)
- Scanning .rpy files and extracting translatable strings
- Translating strings (local or remote endpoint)
- Writing Ren'Py translation files under game/tl/<lang>/
- Previewing changes and applying/rolling back modifications

ADDON (requested):
- Left panel file explorer for game/ tree (folders + files)
- After Analyze: status icon per file (analyzed / not analyzed / useless / impossible)
  + number of extracted dialogue/text lines per script file.
"""

from __future__ import annotations

from pathlib import Path
import re
import requests
import shutil

from core.tl_writer import write_tl_strings_file, write_runtime_filter_assets

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QPlainTextEdit,
    QProgressBar, QLineEdit, QMessageBox, QDialog, QComboBox,
    QListWidget, QTableWidget, QTableWidgetItem, QSplitter, QGroupBox,
    QMenuBar, QToolButton, QSizePolicy,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QStyle
)
from PySide6.QtCore import QThread, Signal, QObject, QSettings, Qt, QPoint
from PySide6.QtGui import QAction, QIcon

from core.project_scanner import (
    detect_renpy_project,
    list_game_rpy_files,
    list_game_archives,
    list_game_compiled_files,
)
from core.packaged_tools import prepare_packaged_game as prepare_packaged_game_workspace
from core.extractor import extract_strings
from core.translator import Translator, TranslatorConfig, TranslationError
from core.rpy_rewriter import rewrite_rpy_file, backup_rpy_file, restore_rpy_file

from app.settings import SettingsDialog, UI_TEXTS
from app.theme import qss_dark


DEFAULT_PUBLIC_ENDPOINT = "https://libretranslate.de/translate"
LOCAL_ENDPOINT = "http://localhost:5000/translate"

LANGUAGES = {
    "English": "en",
    "French": "fr",
    "Spanish": "es",
    "German": "de",
    "Italian": "it",
    "Portuguese": "pt",
    "Japanese": "ja",
    "Chinese": "zh",
    "Arabic": "ar",
    "Russian": "ru",
}

LANG_CODES = ",".join(LANGUAGES.values())


# =====================================================
# Helpers: parse only the patterns we actually rewrite
# (same idea as core/rpy_rewriter.py)
# =====================================================
_RE_DIALOGUE_RW = re.compile(r'^(\s*[A-Za-z_]\w*\s+)"([^"]+)"(\s*)$')
_RE_NARRATION_RW = re.compile(r'^(\s*)"([^"]+)"(\s*)$')
_RE_MENU_CHOICE_RW = re.compile(r'^(\s*)"([^"]+)"(\s*:\s*.*)$')


def _parse_line_rewrite_style(line: str):
    """
    Returns (kind, speaker, text) or None.
    kind: dialogue | narration | menu
    """
    m = _RE_DIALOGUE_RW.match(line)
    if m:
        prefix, text, _suffix = m.groups()
        speaker = prefix.strip().split(" ")[0] if prefix.strip() else "?"
        return ("dialogue", speaker, text)

    m = _RE_MENU_CHOICE_RW.match(line)
    if m:
        _prefix, text, _suffix = m.groups()
        return ("menu", "Menu", text)

    m = _RE_NARRATION_RW.match(line)
    if m:
        _prefix, text, _suffix = m.groups()
        return ("narration", "Narrator", text)

    return None


def _detect_modified_files(game_dir: Path) -> list[Path]:
    modified: list[Path] = []
    for rpy in list_game_rpy_files(game_dir):
        bak = rpy.with_suffix(rpy.suffix + ".bak")
        if not bak.exists():
            continue
        try:
            a = bak.read_text(encoding="utf-8", errors="replace")
            b = rpy.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if a != b:
            modified.append(rpy)
    return modified


def _build_diff_rows(rpy: Path) -> list[tuple[str, str, str]]:
    """
    Returns rows: (character, original_text, translated_text)
    Only includes lines where the rewritten string differs from the backup.
    """
    bak = rpy.with_suffix(rpy.suffix + ".bak")
    if not bak.exists():
        return []

    orig_lines = bak.read_text(encoding="utf-8", errors="replace").splitlines()
    new_lines = rpy.read_text(encoding="utf-8", errors="replace").splitlines()

    rows: list[tuple[str, str, str]] = []
    max_len = max(len(orig_lines), len(new_lines))

    for idx in range(max_len):
        o = orig_lines[idx] if idx < len(orig_lines) else ""
        n = new_lines[idx] if idx < len(new_lines) else ""

        po = _parse_line_rewrite_style(o)
        pn = _parse_line_rewrite_style(n)

        if not po or not pn:
            continue
        kind_o, speaker_o, text_o = po
        kind_n, speaker_n, text_n = pn
        if kind_o != kind_n:
            continue

        if text_o != text_n:
            speaker = speaker_n if speaker_n else speaker_o
            rows.append((speaker, text_o, text_n))

    return rows


# =====================================================
# Changes Viewer Dialog
# =====================================================
class ChangesViewerDialog(QDialog):
    """Dialog that previews changes made to scripts/translation outputs."""
    def __init__(self, game_dir: Path, t_func, parent=None):
        super().__init__(parent)

        self.game_dir = Path(game_dir)
        self.t = t_func

        self.setWindowTitle(self.t("changes_title"))
        self.setMinimumSize(980, 640)

        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        left_box = QGroupBox(self.t("changes_left_title"))
        left_layout = QVBoxLayout(left_box)
        self.file_list = QListWidget()
        left_layout.addWidget(self.file_list)

        right_box = QGroupBox(self.t("changes_right_title"))
        right_layout = QVBoxLayout(right_box)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([
            self.t("col_character"),
            self.t("col_original"),
            self.t("col_translated"),
        ])
        self.table.setWordWrap(True)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        right_layout.addWidget(self.table)

        splitter.addWidget(left_box)
        splitter.addWidget(right_box)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton(self.t("close"))
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.modified_files = _detect_modified_files(self.game_dir)
        if not self.modified_files:
            QMessageBox.information(self, self.t("changes_title"), self.t("changes_none"))
        else:
            for f in self.modified_files:
                rel = str(f.relative_to(self.game_dir)).replace("\\", "/")
                self.file_list.addItem(rel)

        self.file_list.currentRowChanged.connect(self.on_file_selected)

        if self.modified_files:
            self.file_list.setCurrentRow(0)

    def on_file_selected(self, row: int):
        self.table.setRowCount(0)
        if row < 0 or row >= len(self.modified_files):
            return

        f = self.modified_files[row]
        rows = _build_diff_rows(f)

        self.table.setRowCount(len(rows))
        for r, (speaker, orig, trans) in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(speaker))
            self.table.setItem(r, 1, QTableWidgetItem(orig))
            self.table.setItem(r, 2, QTableWidgetItem(trans))

        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()


# =====================================================
# Local Translate Dialog
# =====================================================
class LocalTranslateDialog(QDialog):
    """Dialog to configure a local translation endpoint."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Local translation (advanced)")
        self.setMinimumWidth(720)

        layout = QVBoxLayout(self)

        info = QLabel(
            "<b>Local translation mode (LibreTranslate)</b><br><br>"
            "This mode uses a <b>local</b> translation server (on your PC).<br>"
            "✅ No limits<br>"
            "✅ Often faster<br>"
            "❌ Requires Docker Desktop<br><br>"
            "<b>Languages supported by this app:</b><br>"
            + ", ".join(f"{name} ({code})" for name, code in LANGUAGES.items()) +
            "<br><br>"
            "<b>IMPORTANT:</b> every language you use must be loaded in LibreTranslate.<br><br>"
            "<b>Recommended Docker command (copy/paste):</b>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        command = QPlainTextEdit()
        command.setReadOnly(True)
        command.setPlainText(
            f"docker run -p 5000:5000 libretranslate/libretranslate "
            f"--load-only {LANG_CODES} "
            f"--disable-web-ui"
        )
        layout.addWidget(command)

        self.status = QLabel("🔎 Status: not tested")
        layout.addWidget(self.status)

        row = QHBoxLayout()
        self.test_btn = QPushButton("Test connection")
        self.use_btn = QPushButton("Use localhost")
        self.use_btn.setEnabled(False)

        self.test_btn.clicked.connect(self.test)
        self.use_btn.clicked.connect(self.accept)

        row.addWidget(self.test_btn)
        row.addWidget(self.use_btn)
        layout.addLayout(row)

    def test(self):
        try:
            r = requests.post(
                LOCAL_ENDPOINT,
                json={"q": "Hello", "source": "en", "target": "fr", "format": "text"},
                timeout=5,
                headers={"Accept": "application/json"},
            )
            r.raise_for_status()
            if r.json().get("translatedText"):
                self.status.setText("✅ Local server OK")
                self.use_btn.setEnabled(True)
            else:
                raise RuntimeError("No translatedText in response")
        except Exception:
            self.status.setText(
                "❌ Local server not reachable.\n"
                "Make sure Docker Desktop is running and you executed the command above."
            )


# =====================================================
# Worker
# =====================================================
class TranslateWorker(QObject):
    """Qt worker used to run translation in a background thread."""
    progress = Signal(int)
    log = Signal(str)
    finished = Signal(int, int)  # modified_files, backups_created
    error = Signal(str)

    # batch signals (for 2nd progress bar)
    batch_started = Signal(int, int)   # current_batch, total_batches
    batch_finished = Signal(int, int)  # current_batch, total_batches

    def __init__(self, game_dir: Path, extracted, endpoint: str, src: str, tgt: str):
        super().__init__()
        self.game_dir = Path(game_dir)
        self.extracted = extracted
        self.endpoint = endpoint
        self.src = src
        self.tgt = tgt

    def run(self):
        try:
            backups_created = 0
            rpy_files = list_game_rpy_files(self.game_dir)

            self.log.emit("🛟 Creating backups (*.rpy.bak) before translating…")
            for rpy in rpy_files:
                bak = rpy.with_suffix(rpy.suffix + ".bak")
                if not bak.exists():
                    backup_rpy_file(rpy)
                    backups_created += 1

            if backups_created:
                self.log.emit(f"✅ Backups created: {backups_created}")
            else:
                self.log.emit("ℹ️ Backups already exist (no new backup created).")

            cfg = TranslatorConfig(
                endpoint=self.endpoint,
                source_lang=self.src,
                target_lang=self.tgt,
                timeout_s=30,
            )
            translator = Translator(cfg)

            texts = [i.text for i in self.extracted]
            unique = list(dict.fromkeys(texts))
            total = len(unique)

            self.log.emit(f"🌍 Translating {self.src} → {self.tgt} ({total} strings)")
            self.progress.emit(5)

            def on_progress(done, total_):
                if total_ <= 0:
                    self.progress.emit(65)
                    return
                self.progress.emit(5 + int((done / total_) * 60))

            def on_log(src_text, dst_text):
                self.log.emit(f'✔ "{src_text[:120]}" → "{dst_text[:120]}"')

            def on_batch_start(current_batch: int, total_batches: int):
                self.batch_started.emit(current_batch, total_batches)

            def on_batch_end(current_batch: int, total_batches: int):
                self.batch_finished.emit(current_batch, total_batches)

            translations = translator.translate_many(
                unique,
                progress_cb=on_progress,
                batch_start_cb=on_batch_start,
                batch_end_cb=on_batch_end,
                log_cb=on_log
            )

            self.log.emit("✍️ Writing Ren'Py translation file (game/tl/<lang>/)…")
            self.progress.emit(70)

            out_path = write_tl_strings_file(
                game_dir=self.game_dir,
                lang_code=self.tgt,
                translations=translations,
            )

            map_path, filter_path = write_runtime_filter_assets(
                game_dir=self.game_dir,
                lang_code=self.tgt,
                translations=translations,
            )

            self.log.emit(f"✅ Runtime map: {map_path}")
            self.log.emit(f"✅ Runtime filter: {filter_path}")

            self.log.emit(f"✅ TL file written: {out_path}")
            self.progress.emit(100)

            self.finished.emit(1, backups_created)

        except TranslationError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")


# =====================================================
# Top Bar (Menu + Window Controls)
# =====================================================
class TopBar(QWidget):
    """Custom top bar that hosts the menu and the window controls (min/max/close)."""

    def __init__(self, parent_window: QMainWindow):
        super().__init__(parent_window)
        self._window = parent_window
        self._drag_pos: QPoint | None = None

        self.setObjectName("TopBar")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        # Menu bar (left)
        self.menubar = QMenuBar(self)
        self.menubar.setObjectName("TopMenuBar")
        self.menubar.setNativeMenuBar(False)

        layout.addWidget(self.menubar, 1)

        # Window buttons (right) - 3 dots style
        self.btn_min = QToolButton(self)
        self.btn_min.setObjectName("WinBtnMin")
        self.btn_min.setToolTip("Minimize")
        self.btn_min.setFixedSize(14, 14)
        self.btn_min.clicked.connect(self._window.showMinimized)

        self.btn_max = QToolButton(self)
        self.btn_max.setObjectName("WinBtnMax")
        self.btn_max.setToolTip("Maximize / Restore")
        self.btn_max.setFixedSize(14, 14)
        self.btn_max.clicked.connect(self._toggle_max_restore)

        self.btn_close = QToolButton(self)
        self.btn_close.setObjectName("WinBtnClose")
        self.btn_close.setToolTip("Close")
        self.btn_close.setFixedSize(14, 14)
        self.btn_close.clicked.connect(self._window.close)

        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    def _toggle_max_restore(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    # ---- Drag handling (move the frameless window) ----
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and (e.buttons() & Qt.LeftButton):
            self._window.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        e.accept()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._toggle_max_restore()
            e.accept()


# =====================================================
# Main Window
# =====================================================
class MainWindow(QMainWindow):
    """Main application window: orchestrates scan → translate → write."""
    def __init__(self):
        super().__init__()

        # Frameless window (remove native Windows title bar)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)

        # Custom top bar: menu (left) + window buttons (right)
        self.top_bar = TopBar(self)
        self.setMenuWidget(self.top_bar)

        self.qs = QSettings("RenPyTranslator", "RenPyTranslatorPro")
        self.ui_lang = self.qs.value("ui/lang", "en")
        self.ui_theme = "dark"
        self.endpoint_mode = self.qs.value("net/endpoint_mode", "public")
        self.custom_endpoint = self.qs.value("net/custom_endpoint", DEFAULT_PUBLIC_ENDPOINT)

        if self.ui_lang not in UI_TEXTS:
            self.ui_lang = "en"
        if self.ui_theme not in ("light", "dark"):
            self.ui_theme = "dark"
        if self.endpoint_mode not in ("public", "local"):
            self.endpoint_mode = "public"

        self.setMinimumSize(1050, 650)
        self.resize(1250, 780)

        self.project_root: Path | None = None
        self.game_dir: Path | None = None
        self.original_game_dir: Path | None = None
        self.workspace_root: Path | None = None
        self.extracted = []

        self.thread: QThread | None = None
        self.worker: TranslateWorker | None = None

        # Analysis state for the left tree panel
        self._analysis_ran = False
        self._file_dialogue_counts: dict[str, int] = {}   # relpath -> count
        self._tree_item_by_rel: dict[str, QTreeWidgetItem] = {}

        self._build_menu()

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        # --- Row 1: project picker ---
        row1 = QHBoxLayout()
        self.pick_btn = QPushButton()
        self.pick_btn.clicked.connect(self.pick_project)
        self.project_label = QLabel()
        row1.addWidget(self.pick_btn)
        row1.addWidget(self.project_label, 1)
        layout.addLayout(row1)

        # --- Row 2: endpoint + local ---
        row2 = QHBoxLayout()
        self.endpoint_label = QLabel()
        self.endpoint_edit = QLineEdit()
        self.endpoint_edit.editingFinished.connect(self._save_custom_endpoint_if_needed)
        self.local_btn = QPushButton()
        self.local_btn.clicked.connect(self.open_local)

        row2.addWidget(self.endpoint_label)
        row2.addWidget(self.endpoint_edit, 1)
        row2.addWidget(self.local_btn)
        layout.addLayout(row2)

        # --- Row: languages ---
        row_lang = QHBoxLayout()
        self.src_label = QLabel()
        self.src_combo = QComboBox()
        self.tgt_label = QLabel()
        self.tgt_combo = QComboBox()

        for name, code in LANGUAGES.items():
            self.src_combo.addItem(name, code)
            self.tgt_combo.addItem(name, code)

        self.src_combo.setCurrentText("English")
        self.tgt_combo.setCurrentText("French")

        row_lang.addWidget(self.src_label)
        row_lang.addWidget(self.src_combo)
        row_lang.addWidget(self.tgt_label)
        row_lang.addWidget(self.tgt_combo)
        layout.addLayout(row_lang)

        # --- Row 3: actions ---
        row3 = QHBoxLayout()
        self.analyze_btn = QPushButton()
        self.analyze_btn.clicked.connect(self.analyze)

        self.translate_btn = QPushButton()
        self.translate_btn.clicked.connect(self.start_translation)
        self.translate_btn.setEnabled(False)

        self.restore_btn = QPushButton()
        self.restore_btn.clicked.connect(self.restore_originals)
        self.restore_btn.setEnabled(False)

        self.view_changes_btn = QPushButton()
        self.view_changes_btn.clicked.connect(self.open_changes_viewer)
        self.view_changes_btn.setEnabled(False)

        self.apply_btn = QPushButton()
        self.apply_btn.clicked.connect(self.apply_translation_to_original)
        self.apply_btn.setEnabled(False)

        row3.addWidget(self.analyze_btn)
        row3.addWidget(self.translate_btn)
        row3.addWidget(self.restore_btn)
        row3.addWidget(self.view_changes_btn)
        row3.addWidget(self.apply_btn)
        layout.addLayout(row3)

        # --- Progress bars ---
        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 1)
        self.batch_progress.setValue(0)
        self.batch_progress.setFormat("Batch: idle")
        layout.addWidget(self.batch_progress)

        # =========================================================
        # MAIN SPLITTER: LEFT (game tree) | RIGHT (logs)
        # =========================================================
        self.main_splitter = QSplitter(Qt.Horizontal)

        left_box = QGroupBox("game/ explorer")
        left_layout = QVBoxLayout(left_box)

        self.game_tree = QTreeWidget()
        self.game_tree.setColumnCount(3)
        self.game_tree.setHeaderLabels(["Path", "Status", "Dialogues"])
        self.game_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.game_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.game_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.game_tree.setUniformRowHeights(True)
        self.game_tree.setIndentation(18)
        self.game_tree.itemSelectionChanged.connect(self._on_tree_selection_changed)

        left_layout.addWidget(self.game_tree)

        right_box = QGroupBox("Logs")
        right_layout = QVBoxLayout(right_box)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        right_layout.addWidget(self.log)

        self.main_splitter.addWidget(left_box)
        self.main_splitter.addWidget(right_box)
        self.main_splitter.setStretchFactor(0, 2)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setSizes([420, 830])

        layout.addWidget(self.main_splitter, 1)

        # --- final init ---
        self.apply_theme(self.ui_theme)
        self._apply_saved_endpoint_mode()
        self.retranslate_ui()
        self.clear_log()
        self._refresh_actions_enabled()

    # ---------- i18n ----------
    def t(self, key: str) -> str:
        return UI_TEXTS.get(self.ui_lang, UI_TEXTS["en"]).get(key, UI_TEXTS["en"].get(key, key))

    def retranslate_ui(self):
        self.setWindowTitle(self.t("app_title"))

        self.pick_btn.setText(self.t("pick_game"))
        self.project_label.setText(str(self.project_root) if self.project_root else self.t("no_project"))

        self.endpoint_label.setText(self.t("endpoint"))
        self.local_btn.setText(self.t("local"))

        self.src_label.setText(self.t("src_lang"))
        self.tgt_label.setText(self.t("tgt_lang"))

        self.analyze_btn.setText(self.t("analyze"))
        self.translate_btn.setText(self.t("translate"))
        self.restore_btn.setText(self.t("restore"))
        self.view_changes_btn.setText(self.t("view_changes"))
        self.apply_btn.setText(self.t("apply_to_original"))

        self.menu_home.setTitle(self.t("menu_home"))
        self.menu_project.setTitle(self.t("menu_project"))
        self.menu_tools.setTitle(self.t("menu_tools"))
        self.menu_settings.setTitle(self.t("menu_settings"))
        self.menu_help.setTitle(self.t("menu_help"))

        self.act_home.setText(self.t("act_go_home"))
        self.act_clear_log_home.setText(self.t("act_clear_log"))
        self.act_choose_game.setText(self.t("act_choose_game"))
        self.act_analyze.setText(self.t("act_analyze"))
        self.act_translate.setText(self.t("act_translate"))
        self.act_restore.setText(self.t("act_restore"))
        self.act_view_changes.setText(self.t("act_view_changes"))
        self.act_clear_log_tools.setText(self.t("act_clear_log"))
        self.act_open_settings.setText(self.t("act_preferences"))
        self.act_use_public.setText(self.t("act_use_public"))
        self.act_local_guide.setText(self.t("act_local_guide"))
        self.act_tutorial.setText(self.t("act_tutorial"))
        self.act_about.setText(self.t("act_about"))

        self.act_prepare_packaged.setText(self.t("prepare_packaged"))

    # ---------- theme ----------
    def apply_theme(self, theme: str):
        """Apply the global application theme (QSS)."""
        app = QApplication.instance()
        if not app:
            return
        if theme == "dark":
            app.setStyleSheet(qss_dark())
        else:
            app.setStyleSheet("")

    # ---------- menu ----------
    def _build_menu(self):
        menubar = self.top_bar.menubar

        self.menu_home = menubar.addMenu("Home")
        self.menu_project = menubar.addMenu("Project")
        self.menu_tools = menubar.addMenu("Tools")
        self.menu_settings = menubar.addMenu("Settings")
        self.menu_help = menubar.addMenu("Help")

        self.act_home = QAction("Go to Home", self)
        self.act_home.triggered.connect(self.go_home)
        self.menu_home.addAction(self.act_home)

        self.act_clear_log_home = QAction("Clear logs (reset)", self)
        self.act_clear_log_home.triggered.connect(self.clear_log)
        self.menu_home.addAction(self.act_clear_log_home)

        self.act_choose_game = QAction("Choose game…", self)
        self.act_choose_game.triggered.connect(self.pick_project)
        self.menu_project.addAction(self.act_choose_game)

        self.act_analyze = QAction("Analyze", self)
        self.act_analyze.triggered.connect(self.analyze)
        self.menu_project.addAction(self.act_analyze)

        self.act_translate = QAction("Translate", self)
        self.act_translate.triggered.connect(self.start_translation)
        self.menu_tools.addAction(self.act_translate)

        self.act_restore = QAction("Restore originals (from backup)", self)
        self.act_restore.triggered.connect(self.restore_originals)
        self.menu_tools.addAction(self.act_restore)

        self.act_prepare_packaged = QAction("Prepare packaged game (.rpa/.rpyc)…", self)
        self.act_prepare_packaged.triggered.connect(self.prepare_packaged_game)
        self.menu_tools.addAction(self.act_prepare_packaged)

        self.act_view_changes = QAction("View changes…", self)
        self.act_view_changes.triggered.connect(self.open_changes_viewer)
        self.menu_tools.addAction(self.act_view_changes)

        self.act_clear_log_tools = QAction("Clear logs (reset)", self)
        self.act_clear_log_tools.triggered.connect(self.clear_log)
        self.menu_tools.addAction(self.act_clear_log_tools)

        self.act_open_settings = QAction("Preferences…", self)
        self.act_open_settings.triggered.connect(self.open_settings)
        self.menu_settings.addAction(self.act_open_settings)

        self.menu_settings.addSeparator()

        self.act_use_public = QAction("Use public endpoint", self)
        self.act_use_public.triggered.connect(self.use_public_endpoint)
        self.menu_settings.addAction(self.act_use_public)

        self.act_local_guide = QAction("Local setup guide…", self)
        self.act_local_guide.triggered.connect(self.open_local)
        self.menu_settings.addAction(self.act_local_guide)

        self.act_tutorial = QAction("Tutorial…", self)
        self.act_tutorial.triggered.connect(self.show_tutorial)
        self.menu_help.addAction(self.act_tutorial)

        self.act_about = QAction("About", self)
        self.act_about.triggered.connect(self.show_about)
        self.menu_help.addAction(self.act_about)

    # ---------- persistence ----------
    def _apply_saved_endpoint_mode(self):
        if self.endpoint_mode == "local":
            self.endpoint_edit.setText(LOCAL_ENDPOINT)
        else:
            self.endpoint_edit.setText(self.custom_endpoint or DEFAULT_PUBLIC_ENDPOINT)

    def _save_endpoint_mode(self, mode: str):
        self.endpoint_mode = mode
        self.qs.setValue("net/endpoint_mode", mode)

    def _save_custom_endpoint_if_needed(self):
        txt = self.endpoint_edit.text().strip()
        if txt:
            self.custom_endpoint = txt
            self.qs.setValue("net/custom_endpoint", txt)

    # ---------- UI state ----------
    def _set_busy(self, busy: bool):
        self.pick_btn.setEnabled(not busy)
        self.analyze_btn.setEnabled(not busy)
        self.local_btn.setEnabled(not busy)
        self.endpoint_edit.setEnabled(not busy)
        self.src_combo.setEnabled(not busy)
        self.tgt_combo.setEnabled(not busy)
        self.game_tree.setEnabled(not busy)

        if busy:
            self.translate_btn.setEnabled(False)
            self.restore_btn.setEnabled(False)
            self.view_changes_btn.setEnabled(False)
            self.apply_btn.setEnabled(False)
            self.act_view_changes.setEnabled(False)
        else:
            self._refresh_actions_enabled()

    def _refresh_actions_enabled(self):
        can_restore = self.game_dir is not None
        can_translate = bool(self.extracted) and self.game_dir is not None
        can_view = self.game_dir is not None

        need_prepare_packaged = False
        if self.game_dir is not None:
            has_rpy = bool(list_game_rpy_files(self.game_dir))
            has_packaged = bool(list_game_archives(self.game_dir) or list_game_compiled_files(self.game_dir))
            need_prepare_packaged = (not has_rpy) and has_packaged

        self.translate_btn.setEnabled(can_translate)
        self.restore_btn.setEnabled(can_restore)
        self.view_changes_btn.setEnabled(can_view)
        self.act_view_changes.setEnabled(can_view)

        can_apply = False
        if self.workspace_root and self.original_game_dir and self.game_dir:
            lang = self.tgt_combo.currentData()
            if lang:
                can_apply = (self.game_dir / "tl" / str(lang)).exists()
        self.apply_btn.setEnabled(can_apply)

        self.act_prepare_packaged.setEnabled(need_prepare_packaged)

    # ---------- batch progress handlers ----------
    def _on_batch_started(self, current_batch: int, total_batches: int):
        self.batch_progress.setRange(0, 0)
        self.batch_progress.setValue(0)
        self.batch_progress.setFormat(f"Batch {current_batch}/{total_batches}: translating…")

    def _on_batch_finished(self, current_batch: int, total_batches: int):
        self.batch_progress.setRange(0, 1)
        self.batch_progress.setValue(1)
        self.batch_progress.setFormat(f"Batch {current_batch}/{total_batches}: done")

    def _reset_batch_progress(self):
        self.batch_progress.setRange(0, 1)
        self.batch_progress.setValue(0)
        self.batch_progress.setFormat("Batch: idle")

    # =========================================================
    # LEFT PANEL: tree + analysis statuses
    # =========================================================
    def _std_icon(self, sp: QStyle.StandardPixmap) -> QIcon:
        return self.style().standardIcon(sp)

    def _is_excluded_rel(self, rel: str) -> bool:
        # always ignore tl/ subtree
        rel = rel.replace("\\", "/")
        return rel == "tl" or rel.startswith("tl/") or "/tl/" in rel

    def _path_to_rel(self, p: Path) -> str:
        assert self.game_dir is not None
        return str(p.relative_to(self.game_dir)).replace("\\", "/")

    def _set_item_status(self, item: QTreeWidgetItem, status_text: str, icon: QIcon | None, count: int | None):
        # column 1 = Status, column 2 = Dialogues
        item.setText(1, status_text)
        if icon is not None:
            item.setIcon(1, icon)
        else:
            item.setIcon(1, QIcon())

        if count is None:
            item.setText(2, "")
        else:
            item.setText(2, str(int(count)))

    def _populate_game_tree(self):
        """Build the tree for game/ (folders + files), excluding game/tl/."""
        self.game_tree.clear()
        self._tree_item_by_rel.clear()
        self._analysis_ran = False
        self._file_dialogue_counts = {}

        if not self.game_dir or not self.game_dir.exists():
            return

        root_item = QTreeWidgetItem([self.game_dir.name, "", ""])
        root_item.setIcon(0, self._std_icon(QStyle.SP_DirIcon))
        root_item.setExpanded(True)
        self.game_tree.addTopLevelItem(root_item)

        def add_children(parent_item: QTreeWidgetItem, folder: Path):
            try:
                entries = sorted(folder.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            except Exception:
                return

            for child in entries:
                rel = self._path_to_rel(child)
                if self._is_excluded_rel(rel):
                    continue

                if child.is_dir():
                    it = QTreeWidgetItem([child.name, "", ""])
                    it.setIcon(0, self._std_icon(QStyle.SP_DirIcon))
                    it.setData(0, Qt.UserRole, str(child))
                    parent_item.addChild(it)
                    add_children(it, child)
                else:
                    it = QTreeWidgetItem([child.name, "", ""])
                    it.setIcon(0, self._std_icon(QStyle.SP_FileIcon))
                    it.setData(0, Qt.UserRole, str(child))
                    parent_item.addChild(it)

                    # map only files by rel
                    self._tree_item_by_rel[rel] = it

        add_children(root_item, self.game_dir)

        self.game_tree.expandToDepth(1)
        self._update_tree_status_before_analysis()

    def _update_tree_status_before_analysis(self):
        """Before analyze: mark script files as 'not analyzed yet' and others as N/A/impossible."""
        if not self.game_dir:
            return

        # icons
        ico_pending = self._std_icon(QStyle.SP_BrowserReload)      # 🕒
        ico_na = self._std_icon(QStyle.SP_DialogResetButton)       # ⏺
        ico_block = self._std_icon(QStyle.SP_MessageBoxCritical)   # ⛔

        for rel, item in self._tree_item_by_rel.items():
            rp = rel.lower()

            if rp.endswith(".rpy") or rp.endswith(".rpym"):
                self._set_item_status(item, "🕒 Not analyzed", ico_pending, None)
            elif rp.endswith(".rpa") or rp.endswith(".rpyc") or rp.endswith(".rpyb") or rp.endswith(".rpymc"):
                self._set_item_status(item, "⛔ Not analyzable", ico_block, None)
            else:
                self._set_item_status(item, "⏺ N/A", ico_na, None)

    def _update_tree_status_after_analysis(self, counts: dict[str, int]):
        """After analyze: scripts get analyzed/useless + count; packaged compiled/archives stay blocked."""
        ico_ok = self._std_icon(QStyle.SP_DialogApplyButton)       # ✅
        ico_useless = self._std_icon(QStyle.SP_DialogDiscardButton)  # ➖
        ico_block = self._std_icon(QStyle.SP_MessageBoxCritical)   # ⛔
        ico_na = self._std_icon(QStyle.SP_DialogResetButton)       # ⏺

        for rel, item in self._tree_item_by_rel.items():
            rp = rel.lower()

            if rp.endswith(".rpy") or rp.endswith(".rpym"):
                c = int(counts.get(rel, 0))
                if c > 0:
                    self._set_item_status(item, "✅ Analyzed", ico_ok, c)
                else:
                    # analyzed, but no translatable strings found => "useless to analyze"
                    self._set_item_status(item, "➖ Useless (0)", ico_useless, 0)
            elif rp.endswith(".rpa") or rp.endswith(".rpyc") or rp.endswith(".rpyb") or rp.endswith(".rpymc"):
                self._set_item_status(item, "⛔ Not analyzable", ico_block, None)
            else:
                self._set_item_status(item, "⏺ N/A", ico_na, None)

    def _on_tree_selection_changed(self):
        """Optional: show selected file path in the status bar / logs (no heavy actions)."""
        items = self.game_tree.selectedItems()
        if not items:
            return
        it = items[0]
        p = it.data(0, Qt.UserRole)
        if p:
            self.statusBar().showMessage(str(p))

    # ---------- actions ----------
    def go_home(self):
        self.statusBar().showMessage(self.t("menu_home"))
        self.log.setFocus()

    def clear_log(self):
        self.log.clear()
        self.log.appendPlainText(self.t("ready"))
        self.statusBar().showMessage(self.t("log_cleared"))

    def use_public_endpoint(self):
        self.endpoint_edit.setText(self.custom_endpoint or DEFAULT_PUBLIC_ENDPOINT)
        self._save_endpoint_mode("public")
        self._save_custom_endpoint_if_needed()
        self.statusBar().showMessage(self.t("act_use_public"))

    def show_about(self):
        QMessageBox.information(self, self.t("about_title"), self.t("about_text"))

    def open_settings(self):
        dlg = SettingsDialog(self.ui_lang, self.ui_theme, self.endpoint_mode, self)
        dlg.settings_changed.connect(self.on_settings_changed)
        dlg.exec()

    def on_settings_changed(self, new_lang: str, new_theme: str, new_endpoint_mode: str):
        self.ui_lang = new_lang if new_lang in UI_TEXTS else "en"
        self.ui_theme = "dark"  # forced
        self.endpoint_mode = new_endpoint_mode if new_endpoint_mode in ("public", "local") else "public"

        self.qs.setValue("ui/lang", self.ui_lang)
        self.qs.setValue("ui/theme", "dark")
        self.qs.setValue("net/endpoint_mode", self.endpoint_mode)

        self.apply_theme("dark")
        self._apply_saved_endpoint_mode()
        self.retranslate_ui()

        self.log.appendPlainText("✅ " + self.t("settings_saved"))
        self.statusBar().showMessage(self.t("settings_saved"))

    def pick_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Ren'Py project folder")
        if not folder:
            return

        try:
            proj = detect_renpy_project(folder)
        except Exception as e:
            QMessageBox.critical(self, self.t("error"), str(e))
            return

        self.project_root = proj.root
        self.game_dir = proj.game_dir
        self.original_game_dir = proj.game_dir
        self.workspace_root = None
        self.extracted = []
        self.progress.setValue(0)
        self._reset_batch_progress()

        # refresh left tree
        self._populate_game_tree()

        if self.game_dir is not None:
            has_rpy = bool(list_game_rpy_files(self.game_dir))
            has_packaged = bool(list_game_archives(self.game_dir) or list_game_compiled_files(self.game_dir))
            if (not has_rpy) and has_packaged:
                self.log.appendPlainText("ℹ️ " + self.t("prepare_packaged_hint"))

        self.retranslate_ui()
        self.log.appendPlainText("✅ " + self.t("project_selected"))
        self.statusBar().showMessage(self.t("project_selected"))
        self._refresh_actions_enabled()

    def prepare_packaged_game(self):
        if not self.original_game_dir:
            QMessageBox.warning(self, self.t("missing_project_title"), self.t("missing_project_msg"))
            return

        try:
            result = prepare_packaged_game_workspace(self.original_game_dir)
        except Exception as e:
            QMessageBox.critical(self, self.t("prepare_packaged_error"), str(e))
            self.log.appendPlainText("❌ " + self.t("prepare_packaged_error") + f": {e}")
            return

        self.workspace_root = result.workspace_root
        self.project_root = result.workspace_root
        self.game_dir = result.game_dir
        self.extracted = []
        self.progress.setValue(0)
        self._reset_batch_progress()

        # refresh left tree for workspace game/
        self._populate_game_tree()

        self.retranslate_ui()
        self.log.appendPlainText("✅ " + self.t("prepare_packaged_done"))
        self.log.appendPlainText(f"📁 Workspace: {self.workspace_root}")
        self.statusBar().showMessage(self.t("prepare_packaged_done"))
        self._refresh_actions_enabled()

    def analyze(self):
        if not self.game_dir:
            QMessageBox.warning(self, self.t("missing_project_title"), self.t("missing_project_msg"))
            return

        result = extract_strings(self.game_dir)
        self.extracted = result.items

        # Build counts per file (rel path)
        counts: dict[str, int] = {}
        for it in self.extracted:
            # it.file is already a rel path from game_dir in core/rpy_parser.py
            rel = (it.file or "").replace("\\", "/")
            if not rel:
                continue
            if self._is_excluded_rel(rel):
                continue
            counts[rel] = counts.get(rel, 0) + 1

        self._analysis_ran = True
        self._file_dialogue_counts = counts
        self._update_tree_status_after_analysis(counts)

        self.log.appendPlainText("✅ Project loaded.")
        self.log.appendPlainText(
            f"📄 Files: .rpy/.rpym={result.total_files} | "
            f".rpyc/.rpymc/.rpyb={len(list_game_compiled_files(self.game_dir))} | "
            f".rpa={len(list_game_archives(self.game_dir))}"
        )
        self.log.appendPlainText(f"🧩 Extracted strings (dialogue/narration/menu/ui): {len(self.extracted)}")
        self.log.appendPlainText("📌 Left panel updated: status icons + dialogue count per script.")

        self.statusBar().showMessage(self.t("analysis_done"))
        self._refresh_actions_enabled()

    def start_translation(self):
        if not self.game_dir:
            QMessageBox.warning(self, self.t("missing_project_title"), self.t("missing_project_msg"))
            return
        if not self.extracted:
            QMessageBox.warning(self, self.t("missing_analysis_title"), self.t("missing_analysis_msg"))
            return

        src = self.src_combo.currentData()
        tgt = self.tgt_combo.currentData()
        if src == tgt:
            QMessageBox.warning(self, self.t("invalid_languages_title"), self.t("invalid_languages_msg"))
            return

        endpoint = self.endpoint_edit.text().strip()
        if not endpoint:
            QMessageBox.warning(self, self.t("missing_endpoint_title"), self.t("missing_endpoint_msg"))
            return

        self._save_custom_endpoint_if_needed()

        self.progress.setValue(0)
        self._reset_batch_progress()
        self.log.appendPlainText("—" * 45)
        self.statusBar().showMessage(self.t("translating"))
        self._set_busy(True)

        self.thread = QThread()
        self.worker = TranslateWorker(self.game_dir, self.extracted, endpoint, src, tgt)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.log.connect(self.log.appendPlainText)

        self.worker.batch_started.connect(self._on_batch_started)
        self.worker.batch_finished.connect(self._on_batch_finished)

        self.worker.finished.connect(self.on_translation_finished)
        self.worker.error.connect(self.on_translation_error)

        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_translation_finished(self, modified_files: int, backups_created: int):
        if self.thread:
            self.thread.quit()
            self.thread.wait(3000)

        self._set_busy(False)
        self._reset_batch_progress()
        self.statusBar().showMessage(self.t("translation_finished"))
        self._refresh_actions_enabled()

        QMessageBox.information(
            self,
            self.t("translation_finished"),
            f"Modified files: {modified_files}\nNew backups created: {backups_created}\n\n"
            f"{self.t('restore')}"
        )

    def on_translation_error(self, msg: str):
        if self.thread:
            self.thread.quit()
            self.thread.wait(3000)

        self._set_busy(False)
        self._reset_batch_progress()
        self.statusBar().showMessage(self.t("error"))
        QMessageBox.critical(self, self.t("error"), msg)

    def show_tutorial(self):
        QMessageBox.information(self, self.t("tutorial_title"), self.t("tutorial_text"))

    def apply_translation_to_original(self):
        """When working on a packaged game workspace, copy tl/<lang>/ back into the original game folder."""
        if not self.workspace_root or not self.original_game_dir or not self.game_dir:
            QMessageBox.warning(self, self.t("apply_title"), self.t("apply_not_packaged"))
            return

        lang = self.tgt_combo.currentData()
        if not lang:
            QMessageBox.warning(self, self.t("apply_title"), self.t("apply_missing_lang"))
            return

        src_dir = Path(self.game_dir) / "tl" / str(lang)
        if not src_dir.exists():
            QMessageBox.warning(self, self.t("apply_title"), self.t("apply_nothing_to_apply"))
            return

        dst_dir = Path(self.original_game_dir) / "tl" / str(lang)

        answer = QMessageBox.question(
            self,
            self.t("apply_title"),
            self.t("apply_confirm"),
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            dst_dir.mkdir(parents=True, exist_ok=True)

            for p in src_dir.rglob("*"):
                if p.is_dir():
                    continue
                rel = p.relative_to(src_dir)
                out = dst_dir / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, out)

            self.log.appendPlainText("✅ " + self.t("apply_done") + f" ({lang})")
            self.log.appendPlainText(f"📌 {dst_dir}")
            QMessageBox.information(self, self.t("apply_title"), self.t("apply_done"))
        except Exception as e:
            self.log.appendPlainText("❌ " + self.t("apply_error") + f": {e}")
            QMessageBox.critical(self, self.t("apply_title"), self.t("apply_error") + f"\n\n{e}")

    def restore_originals(self):
        if not self.game_dir:
            QMessageBox.warning(self, self.t("missing_project_title"), self.t("missing_project_msg"))
            return

        answer = QMessageBox.question(
            self,
            self.t("restore"),
            "This will restore every .rpy file from its .bak backup.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return

        restored = 0
        missing = 0
        for rpy in list_game_rpy_files(self.game_dir):
            bak = rpy.with_suffix(rpy.suffix + ".bak")
            if bak.exists():
                restore_rpy_file(rpy)
                restored += 1
            else:
                missing += 1

        self.progress.setValue(0)
        self.log.appendPlainText("—" * 45)
        self.log.appendPlainText(f"🛟 Restored: {restored}. Missing backups: {missing}.")
        self.statusBar().showMessage(self.t("restore_finished"))

    def open_local(self):
        dlg = LocalTranslateDialog(self)
        if dlg.exec():
            self.endpoint_edit.setText(LOCAL_ENDPOINT)
            self._save_endpoint_mode("local")
            self.statusBar().showMessage("Local mode enabled.")

    def open_changes_viewer(self):
        if not self.game_dir:
            QMessageBox.warning(self, self.t("missing_project_title"), self.t("missing_project_msg"))
            return
        dlg = ChangesViewerDialog(self.game_dir, self.t, self)
        dlg.exec()