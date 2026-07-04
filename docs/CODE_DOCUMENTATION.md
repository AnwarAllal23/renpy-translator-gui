# Ren'Py Translator - Technical Code Documentation

Version: 0.3.0

This document describes the internal architecture of Ren'Py Translator for
maintainers, contributors, and release builders. It complements the user-facing
README and focuses on code responsibilities, data flow, safety guarantees, and
extension points.

## 1. Product Overview

Ren'Py Translator is a PySide6 desktop application that scans Ren'Py game
scripts, extracts user-visible text, translates it with a selected provider,
and writes Ren'Py-compatible translation assets under `game/tl/<language>/`.

The application supports two project shapes:

- Source projects containing editable `.rpy` or `.rpym` files.
- Packaged games containing `.rpa` archives and compiled `.rpyc`-family files.

The main design principle is conservative modification. The original game files
are either left untouched through generated `tl/` assets, or backed up before
direct rewrite operations.

## 2. Runtime Entry Point

### `entrypoint.py`

Responsibilities:

- Installs the global exception hook.
- Creates the Qt `QApplication`.
- Applies the dark stylesheet.
- Displays the startup splash screen.
- Creates and shows `MainWindow`.
- Optionally accepts a project path as the first command-line argument.

Important functions:

- `main()`: application bootstrap and Qt event loop.
- `_create_splash()`: builds the branded loading screen shown before the main
  window is displayed.
- `_show_loading_step()`: updates splash text while keeping Qt responsive.

The splash screen is intentionally created before `MainWindow`, so users see a
loading state while settings, UI widgets, and optional startup project state are
prepared.

## 3. Application Metadata

### `app/version.py`

Single source of truth for product identity:

- `APP_NAME`
- `APP_EDITION`
- `APP_VERSION`
- `APP_DISPLAY_NAME`
- `APP_DISPLAY_VERSION`

Every visible version string should import from this module. This prevents
release metadata from drifting across the UI, documentation, and packaging
configuration.

## 4. User Interface Layer

### `app/main_window.py`

This is the central UI orchestration module. It owns the complete desktop
workflow:

- Project selection and detection.
- Packaged-game workspace preparation.
- Script analysis.
- Translation job creation.
- Progress display.
- Log display.
- Restore/apply actions.
- Menus, dialogs, and status bar.

Key classes:

- `MainWindow`: main frameless application window.
- `TopBar`: custom title/menu bar with window controls.
- `TranslateWorker`: background worker used to run translation without blocking
  the UI thread.
- `ChangesViewerDialog`: side-by-side preview of changed lines.
- `LocalTranslateDialog`: helper dialog for local LibreTranslate setup.

Important UI state:

- `project_root`: selected project root.
- `game_dir`: active `game/` directory. For packaged games this may point to the
  generated workspace.
- `original_game_dir`: real game directory used when applying workspace output
  back to the original game.
- `workspace_root`: generated workspace for packaged games.
- `extracted`: current extraction result used by translation.

Threading model:

- Translation work runs in `TranslateWorker` moved into a `QThread`.
- The worker communicates through Qt signals only.
- UI widgets are updated by slots on the main thread.

Status/version display:

- The status bar shows transient workflow messages.
- A permanent bottom-right label displays `v<APP_VERSION>`.

### `app/settings.py`

Responsibilities:

- Stores UI copy for English, French, and Spanish.
- Provides `SettingsDialog`.
- Emits settings changes back to `MainWindow`.

The `UI_TEXTS` dictionary is the current i18n mechanism. New visible labels
should be added in every supported language to avoid mixed-language UI.

### `app/theme.py`

Responsibilities:

- Provides `qss_dark()`, the dark application stylesheet.
- Styles the frameless shell, cards, controls, log console, progress bars,
  status bar, and version label.

Qt stylesheets are used for static styling. Runtime shadows are applied in
`MainWindow._add_card_shadow()` because QSS does not support `box-shadow`.

## 5. Core Domain Layer

### `core/project_scanner.py`

Responsibilities:

- Detects whether a selected folder is a Ren'Py project.
- Locates the active `game/` directory.
- Lists source scripts, archives, and compiled script files.

Main functions:

- `detect_renpy_project(folder)`
- `list_game_rpy_files(game_dir)`
- `list_game_archives(game_dir)`
- `list_game_compiled_files(game_dir)`

This module is intentionally filesystem-focused and does not parse script
contents.

### `core/extractor.py`

Responsibilities:

- Provides a stable high-level extraction API for the UI.
- Iterates over `.rpy`/`.rpym` files.
- Delegates actual parsing to `core/rpy_parser.py`.

Main data type:

- `ExtractionResult`: contains extracted items and the number of scanned files.

Main function:

- `extract_strings(game_dir)`

### `core/rpy_parser.py`

Responsibilities:

- Extracts user-visible strings from Ren'Py script files.
- Avoids existing translation blocks.
- Avoids technical blocks such as `python`, `init`, `style`, `transform`, and
  `define`.
- Extracts selected UI strings inside `screen` blocks.

Main data type:

- `ExtractedString`: kind, text, file, line, speaker, and context.

Supported extraction categories:

- `dialogue`: speaker-based Ren'Py say lines.
- `narration`: bare quoted narration lines.
- `menu`: menu choice text.
- `ui`: selected screen UI strings such as `text`, `textbutton`, `label`, and
  `tooltip`.

Parser philosophy:

The parser uses conservative line-based heuristics instead of a full Ren'Py AST.
This keeps the implementation lightweight and robust across many real-world
scripts, but it also means tests are essential for edge cases.

### `core/translator.py`

Responsibilities:

- Defines translation provider configuration.
- Protects Ren'Py-sensitive tokens before translation.
- Sends batches to the selected translation engine.
- Restores protected tokens after translation.
- Maintains an in-memory translation cache.

Supported providers:

- LibreTranslate public or local endpoint.
- Argos Translate offline.
- Google Translate API.
- DeepL API.

Key classes:

- `TranslatorConfig`
- `TranslationError`
- `Translator`

Important safety behavior:

- Ren'Py text tags, interpolation markers, escaped line breaks, escaped quotes,
  and percent-format placeholders are replaced with stable temporary tokens
  before text is sent to a provider.
- Tokens are restored after provider output returns.
- Literal percent signs are escaped for Ren'Py output.

Argos behavior:

- The language package is installed on first use if missing.
- The first translation call is warmed up before concurrent workers are used.
- Worker count is tuned to use CPU cores unless the user has explicitly set
  Argos/CTranslate2 environment variables.

### `core/tl_writer.py`

Responsibilities:

- Writes Ren'Py translation files under `game/tl/<lang>/`.
- Writes runtime filter assets for say/menu text.

Generated files:

- `zz_auto_strings.rpy`: Ren'Py `translate <lang> strings:` block.
- `rt_map.json`: old-to-new runtime translation map.
- `zz_runtime_filter.rpy`: installs `config.say_menu_text_filter`.

Safety behavior:

- Empty translations are skipped.
- Color-like strings are skipped.
- Quotes and backslashes are escaped for Ren'Py string syntax.

### `core/rpy_rewriter.py`

Responsibilities:

- Creates `.rpy.bak` backups.
- Restores original files from backups.
- Optionally rewrites source `.rpy` files with translated strings.

This module mirrors many parser safety rules because rewriting is higher risk
than generating `tl/` assets. It avoids technical blocks and Ren'Py statements
that may contain quoted strings but are not user-facing dialogue.

### `core/packaged_tools.py`

Responsibilities:

- Creates a safe workspace for packaged games.
- Copies the original game into that workspace.
- Extracts `.rpa` archives.
- Attempts to decompile compiled script files on a best-effort basis.

The original game directory is not modified during workspace preparation.
Generated translation output can later be copied back through the UI.

### `core/rpa_extractor.py`

Responsibilities:

- Extracts Ren'Py archive files.
- Isolates archive-specific extraction details from the workspace orchestration.

Archive handling should stay separated from UI code so extractor behavior can
be tested and replaced independently.

### `core/docker_manager.py`

Responsibilities:

- Detects Docker availability.
- Starts or creates the local LibreTranslate container.
- Waits for the local API to become reachable.

This module is used only for LibreTranslate local mode. Argos Translate remains
the offline path that does not require Docker.

### `core/log_setup.py`

Responsibilities:

- Configures persistent rotating logs.
- Exposes the active log file path.
- Installs a global uncaught-exception hook.

Persistent logs are important because the UI log panel is volatile and can be
lost on crash or restart.

## 6. End-to-End Workflow

### Source project flow

1. User selects a Ren'Py project folder.
2. `detect_renpy_project()` resolves the project and `game/` directory.
3. `extract_strings()` scans `.rpy` and `.rpym` files.
4. `Translator.translate_many()` translates unique extracted strings in batches.
5. `write_tl_strings_file()` writes static Ren'Py translation strings.
6. `write_runtime_filter_assets()` writes runtime say/menu filter assets.
7. User tests the game in Ren'Py.

### Packaged game flow

1. User selects a packaged game folder.
2. UI detects no source `.rpy` files but finds archives or compiled scripts.
3. User runs packaged-game preparation.
4. `prepare_packaged_game()` creates a workspace copy.
5. Archives are extracted and compiled scripts are decompiled where possible.
6. The normal source-project flow runs inside the workspace.
7. User applies generated `tl/<lang>/` output back to the original game.

## 7. Translation Safety Rules

Never translate or alter these Ren'Py-sensitive fragments:

- Text tags: `{i}`, `{/i}`, `{color=#fff}`, etc.
- Interpolations: `[player_name]`, `[score]`, `[config.version]`, etc.
- Percent placeholders: `%s`, `%d`, `%(name)s`, etc.
- Escaped syntax: `\\n`, `\\"`.

The translation layer protects these before provider calls. The writer and
rewriter then escape output for Ren'Py syntax.

## 8. Packaging

### `RenPyTranslator.spec`

PyInstaller spec used to build a standalone app from `entrypoint.py`.

Current behavior:

- Windowed app (`console=False`).
- Uses PyInstaller analysis of Python imports.
- Builds platform-native output on the current operating system.

Important limitation:

PyInstaller does not truly cross-compile. A Windows `.exe` should be built on
Windows, and a macOS `.app` should be built on macOS. A macOS machine can test
the macOS build locally, but it cannot reliably produce a native Windows exe
without a dedicated Windows environment.

## 9. Recommended Test Areas

High-value tests should cover:

- Parser extraction for dialogue, narration, menu choices, and UI strings.
- Parser skipping for `translate`, `python`, `init`, `style`, and technical
  statements.
- Token protection and restoration in `Translator`.
- Ren'Py escaping in `tl_writer`.
- Backup and restore behavior in `rpy_rewriter`.
- Workspace creation logic for packaged games.

## 10. Extension Points

Add a translation provider:

1. Add provider key to `ENGINES` in `app/main_window.py`.
2. Add UI handling in `_on_engine_changed()`.
3. Add validation in `start_translation()`.
4. Add provider routing in `Translator._translate_raw_batch()`.
5. Implement `_raw_<provider>()`.
6. Add documentation and tests.

Add a UI language:

1. Add a new language entry to `UI_TEXTS`.
2. Add it to `SettingsDialog`.
3. Check every visible string in `MainWindow` and dialogs.

Add a supported game language:

1. Add display name and code to `LANGUAGES`.
2. Verify provider support for that code.
3. Update Docker `--load-only` language list if relevant.

## 11. Maintenance Notes

- Keep `app/version.py` as the only release version source.
- Do not commit `__pycache__`, build output, virtual environments, or generated
  game backup files.
- Prefer generated `tl/` assets over direct source rewrites when possible.
- Treat Ren'Py syntax preservation as a correctness requirement, not polish.
- Keep provider failures explicit and visible in persistent logs.
