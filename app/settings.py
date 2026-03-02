"""Ren'Py Translator - Settings dialog and persistence.

The SettingsDialog is responsible for:
- Showing user preferences (language, endpoint mode)
- Validating user inputs
- Emitting settings_changed
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout,
    QLabel, QPushButton, QComboBox
)
from PySide6.QtCore import Signal


UI_TEXTS = {
    "en": {
        # App
        "app_title": "Ren'Py Translator — Pro",
        "ready": "Ready.",
        "log_cleared": "Log cleared.",
        "settings_saved": "Settings saved.",
        "project_selected": "Project selected.",
        "prepare_packaged": "Prepare packaged game (.rpa/.rpyc)…",
        "prepare_packaged_done": "Packaged game workspace ready.",
        "prepare_packaged_hint": "No .rpy sources found — use Tools → Prepare packaged game.",
        "prepare_packaged_error": "Prepare packaged game failed.",
        "analysis_done": "Analysis done.",
        "translating": "Translating…",
        "translation_finished": "Translation finished.",
        "restore_finished": "Restore finished.",
        "error": "Error.",

        # Main UI
        "pick_game": "Choose game",
        "no_project": "No project selected.",
        "endpoint": "Endpoint:",
        "local": "Local (advanced)",
        "src_lang": "Source language:",
        "tgt_lang": "Target language:",
        "analyze": "Analyze",
        "translate": "Translate",
        "restore": "Restore original (from backup)",
        "view_changes": "View changes",

        # Changes viewer
        "changes_title": "Changes viewer",
        "changes_left_title": "Modified files",
        "changes_right_title": "Modified lines",
        "changes_none": "No modified files found. (No .bak diff)",
        "col_character": "Character",
        "col_original": "Original (source)",
        "col_translated": "Translated",
        "close": "Close",

        # Warnings / messages
        "missing_project_title": "Missing project",
        "missing_project_msg": "Please choose a Ren'Py project first.",
        "missing_analysis_title": "Missing analysis",
        "missing_analysis_msg": "Please click Analyze first.",
        "invalid_languages_title": "Invalid languages",
        "invalid_languages_msg": "Source and target languages must be different.",
        "missing_endpoint_title": "Missing endpoint",
        "missing_endpoint_msg": "Please enter a translation endpoint.",

        # Menus
        "menu_home": "Home",
        "menu_project": "Project",
        "menu_tools": "Tools",
        "menu_settings": "Settings",
        "menu_help": "Help",

        # Actions
        "act_go_home": "Go to Home",
        "act_clear_log": "Clear logs (reset)",
        "act_choose_game": "Choose game…",
        "act_analyze": "Analyze",
        "act_translate": "Translate",
        "act_restore": "Restore originals (from backup)",
        "act_view_changes": "View changes…",
        "act_preferences": "Preferences…",
        "act_use_public": "Use public endpoint",
        "act_local_guide": "Local setup guide…",
        "act_about": "About",

        # About
        "about_title": "About",
        "about_text":
            "Ren'Py Translator — Pro\n\n"
            "• Translates dialogue/narration/menu choices in .rpy files\n"
            "• Creates .bak backups automatically before translating\n"
            "• Restore originals anytime from backups\n",

        # Settings dialog
        "settings": "Settings",
        "language": "Application language",
        "endpoint_mode": "Translation endpoint",
        "endpoint_public": "Public (online)",
        "endpoint_local": "Local (localhost)",
        "save": "Save",
        "cancel": "Cancel",

        # Misc
        "restore_done": "Restore done.",

        "apply_to_original": "Apply to original game",
        "apply_title": "Apply translation",
        "apply_confirm": "This will copy the generated translation back into the ORIGINAL game folder (game/tl/<lang>/).\n\nContinue?",
        "apply_done": "Translation copied to original game.",
        "apply_error": "Failed to apply translation.",
        "apply_not_packaged": "This button is only useful when you prepared a packaged game (workspace).",
        "apply_missing_lang": "No target language selected.",
        "apply_nothing_to_apply": "No tl/<lang>/ folder found in the workspace. Translate first.",

        "act_tutorial": "How to translate a Ren'Py game…",
        "tutorial_title": "Ren'Py translation tutorial",
        "tutorial_text": (
            "Step 1 — Choose the game\n"
            "• Click ‘Choose game’ and select the project folder (the one that contains game/).\n\n"
            "Step 2 — If the game is PACKAGED\n"
            "• If the tool warns that there are no .rpy sources, go to Tools → Prepare packaged game.\n"
            "• This creates a workspace where .rpa are extracted and compiled scripts are decompiled (best effort).\n\n"
            "Step 3 — Analyze\n"
            "• Click Analyze to scan scripts and extract user-visible strings (dialogue, narration, menu, some UI).\n\n"
            "Step 4 — Pick languages\n"
            "• Source language = the language currently in the game.\n"
            "• Target language = the language you want (ex: French = fr).\n\n"
            "Step 5 — Choose a translation endpoint\n"
            "• Public: uses an online LibreTranslate endpoint (may be rate-limited).\n"
            "• Local (advanced): run LibreTranslate with Docker, then click Local.\n\n"
            "Step 6 — Translate\n"
            "• Click Translate. The app generates: game/tl/<lang>/zz_auto_strings.rpy + runtime filter files.\n"
            "• The tl/<lang>/ folder is created automatically if missing.\n\n"
            "Step 7 — Apply (only for packaged workspace)\n"
            "• If you used a workspace, click ‘Apply to original game’ to copy tl/<lang>/ into the real game folder.\n\n"
            "Step 8 — Test in Ren'Py\n"
            "• Start the game, then switch language in Ren'Py (Preferences / Language) if available.\n"
        ),
    },

    "fr": {
        "app_title": "Ren'Py Translator — Pro",
        "ready": "Prêt.",
        "log_cleared": "Journal effacé.",
        "settings_saved": "Paramètres enregistrés.",
        "project_selected": "Projet sélectionné.",
        "prepare_packaged": "Préparer un jeu packagé (.rpa/.rpyc)…",
        "prepare_packaged_done": "Espace de travail prêt pour le jeu packagé.",
        "prepare_packaged_hint": "Aucun fichier .rpy trouvé — utilise Outils → Préparer un jeu packagé.",
        "prepare_packaged_error": "Échec de la préparation du jeu packagé.",
        "analysis_done": "Analyse terminée.",
        "translating": "Traduction…",
        "translation_finished": "Traduction terminée.",
        "restore_finished": "Restauration terminée.",
        "error": "Erreur.",

        "pick_game": "Choisir un jeu",
        "no_project": "Aucun projet sélectionné.",
        "endpoint": "Endpoint :",
        "local": "Local (avancé)",
        "src_lang": "Langue source :",
        "tgt_lang": "Langue cible :",
        "analyze": "Analyser",
        "translate": "Traduire",
        "restore": "Restaurer l'original (backup)",
        "view_changes": "Voir les changements",

        "changes_title": "Visionneuse de changements",
        "changes_left_title": "Fichiers modifiés",
        "changes_right_title": "Lignes modifiées",
        "changes_none": "Aucun fichier modifié trouvé. (Pas de diff avec .bak)",
        "col_character": "Personnage",
        "col_original": "Original (source)",
        "col_translated": "Traduit",
        "close": "Fermer",

        "missing_project_title": "Projet manquant",
        "missing_project_msg": "Choisis d'abord un projet Ren'Py.",
        "missing_analysis_title": "Analyse manquante",
        "missing_analysis_msg": "Clique sur Analyser d'abord.",
        "invalid_languages_title": "Langues invalides",
        "invalid_languages_msg": "La langue source et la langue cible doivent être différentes.",
        "missing_endpoint_title": "Endpoint manquant",
        "missing_endpoint_msg": "Entre un endpoint de traduction.",

        "menu_home": "Accueil",
        "menu_project": "Projet",
        "menu_tools": "Outils",
        "menu_settings": "Paramètres",
        "menu_help": "Aide",

        "act_go_home": "Aller à l'accueil",
        "act_clear_log": "Effacer les logs (reset)",
        "act_choose_game": "Choisir un jeu…",
        "act_analyze": "Analyser",
        "act_translate": "Traduire",
        "act_restore": "Restaurer depuis backup",
        "act_view_changes": "Voir les changements…",
        "act_preferences": "Préférences…",
        "act_use_public": "Utiliser l'endpoint public",
        "act_local_guide": "Guide local…",
        "act_about": "À propos",

        "about_title": "À propos",
        "about_text":
            "Ren'Py Translator — Pro\n\n"
            "• Traduit les textes (dialogue/narration/choix menu) dans les fichiers .rpy\n"
            "• Crée automatiquement des backups .bak avant de traduire\n"
            "• Restaure les originaux à tout moment\n",

        "settings": "Paramètres",
        "language": "Langue de l'application",
        "endpoint_mode": "Endpoint de traduction",
        "endpoint_public": "Public (en ligne)",
        "endpoint_local": "Local (localhost)",
        "save": "Enregistrer",
        "cancel": "Annuler",

        "restore_done": "Restauration terminée.",

        "apply_to_original": "Appliquer au jeu original",
        "apply_title": "Appliquer la traduction",
        "apply_confirm": "Ça va copier la traduction générée vers le dossier ORIGINAL du jeu (game/tl/<lang>/).\n\nContinuer ?",
        "apply_done": "Traduction copiée dans le jeu original.",
        "apply_error": "Échec de l'application de la traduction.",
        "apply_not_packaged": "Ce bouton sert surtout quand tu as préparé un jeu packagé (workspace).",
        "apply_missing_lang": "Aucune langue cible sélectionnée.",
        "apply_nothing_to_apply": "Aucun dossier tl/<lang>/ trouvé dans le workspace. Traduis d'abord.",

        "act_tutorial": "Tutoriel : traduire un jeu Ren'Py…",
        "tutorial_title": "Tutoriel de traduction Ren'Py",
        "tutorial_text": "Voir l'aide dans l'app.",
    },

    "es": {
        "app_title": "Ren'Py Translator — Pro",
        "ready": "Listo.",
        "log_cleared": "Registro borrado.",
        "settings_saved": "Preferencias guardadas.",
        "project_selected": "Proyecto seleccionado.",
        "prepare_packaged": "Preparar juego empaquetado (.rpa/.rpyc)…",
        "prepare_packaged_done": "Espacio de trabajo listo para el juego empaquetado.",
        "prepare_packaged_hint": "No se encontraron .rpy — usa Herramientas → Preparar juego empaquetado.",
        "prepare_packaged_error": "Falló la preparación del juego empaquetado.",
        "analysis_done": "Análisis listo.",
        "translating": "Traduciendo…",
        "translation_finished": "Traducción terminada.",
        "restore_finished": "Restauración terminada.",
        "error": "Error.",

        "pick_game": "Elegir juego",
        "no_project": "Ningún proyecto seleccionado.",
        "endpoint": "Endpoint:",
        "local": "Local (avanzado)",
        "src_lang": "Idioma origen:",
        "tgt_lang": "Idioma destino:",
        "analyze": "Analizar",
        "translate": "Traducir",
        "restore": "Restaurar original (backup)",
        "view_changes": "Ver cambios",

        "changes_title": "Visor de cambios",
        "changes_left_title": "Archivos modificados",
        "changes_right_title": "Líneas modificadas",
        "changes_none": "No se encontraron archivos modificados. (Sin diff con .bak)",
        "col_character": "Personaje",
        "col_original": "Original (origen)",
        "col_translated": "Traducido",
        "close": "Cerrar",

        "missing_project_title": "Falta proyecto",
        "missing_project_msg": "Primero elige un proyecto Ren'Py.",
        "missing_analysis_title": "Falta análisis",
        "missing_analysis_msg": "Pulsa Analizar primero.",
        "invalid_languages_title": "Idiomas inválidos",
        "invalid_languages_msg": "El idioma origen y destino deben ser diferentes.",
        "missing_endpoint_title": "Falta endpoint",
        "missing_endpoint_msg": "Introduce un endpoint de traducción.",

        "menu_home": "Inicio",
        "menu_project": "Proyecto",
        "menu_tools": "Herramientas",
        "menu_settings": "Ajustes",
        "menu_help": "Ayuda",

        "act_go_home": "Ir a inicio",
        "act_clear_log": "Borrar logs (reset)",
        "act_choose_game": "Elegir juego…",
        "act_analyze": "Analizar",
        "act_translate": "Traducir",
        "act_restore": "Restaurar desde backup",
        "act_view_changes": "Ver cambios…",
        "act_preferences": "Preferencias…",
        "act_use_public": "Usar endpoint público",
        "act_local_guide": "Guía local…",
        "act_about": "Acerca de",

        "about_title": "Acerca de",
        "about_text": "Ren'Py Translator — Pro",

        "settings": "Configuración",
        "language": "Idioma de la aplicación",
        "endpoint_mode": "Servidor de traducción",
        "endpoint_public": "Público (online)",
        "endpoint_local": "Local (localhost)",
        "save": "Guardar",
        "cancel": "Cancelar",
    },
}


class SettingsDialog(QDialog):
    """
    Settings dialog: we keep ONLY language + endpoint mode.
    Theme is forced to "dark" (no UI toggle).
    """
    # Keep signature (lang, theme, endpoint_mode) for compatibility with MainWindow.on_settings_changed
    settings_changed = Signal(str, str, str)

    def __init__(self, current_lang: str, _current_theme: str, current_endpoint_mode: str, parent=None):
        super().__init__(parent)

        self.lang = current_lang if current_lang in UI_TEXTS else "en"
        self.theme = "dark"  # ✅ forced
        self.endpoint_mode = current_endpoint_mode if current_endpoint_mode in ("public", "local") else "public"

        t = UI_TEXTS[self.lang]

        self.setWindowTitle(t["settings"])
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(t["language"]))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Français", "fr")
        self.lang_combo.addItem("Español", "es")
        self.lang_combo.setCurrentIndex(self.lang_combo.findData(self.lang))
        layout.addWidget(self.lang_combo)

        layout.addWidget(QLabel(t["endpoint_mode"]))
        self.endpoint_combo = QComboBox()
        self.endpoint_combo.addItem(t["endpoint_public"], "public")
        self.endpoint_combo.addItem(t["endpoint_local"], "local")
        self.endpoint_combo.setCurrentIndex(self.endpoint_combo.findData(self.endpoint_mode))
        layout.addWidget(self.endpoint_combo)

        self.save_btn = QPushButton(t["save"])
        self.save_btn.clicked.connect(self.apply_and_close)
        layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton(t["cancel"])
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)

    def apply_and_close(self):
        # Emit "dark" theme without requiring any theme_combo widget.
        self.settings_changed.emit(
            self.lang_combo.currentData(),
            "dark",
            self.endpoint_combo.currentData(),
        )
        self.accept()