"""Ren'Py Translator - Detect and inspect Ren'Py projects.

Functions here find the 'game' directory, list scripts, archives, and compiled
files, and provide basic heuristics to determine whether a selected folder is a
Ren'Py project.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RenpyProject:
    """Simple data container describing a detected Ren'Py project."""
    root: Path
    game_dir: Path


def detect_renpy_project(selected_path: str) -> RenpyProject:
    """
    Detect a Ren'Py project folder.

    Accepts:
    - a project root containing game/
    - the game/ directory itself

    IMPORTANT: some distributed games contain no .rpy sources (only .rpa/.rpyc/.rpyb/.rpymc).
    In that case, this function still accepts the project, and the UI can offer a
    "Prepare packaged game" step to extract/decompile scripts into a workspace.
    """
    root = Path(selected_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError("Chemin invalide.")

    if root.name.lower() == "game":
        game_dir = root
        root = root.parent
    else:
        game_dir = root / "game"

    if not game_dir.exists() or not game_dir.is_dir():
        raise ValueError("Ce dossier ne contient pas de répertoire 'game/' (pas un projet Ren'Py).")

    if (
        not list_game_rpy_files(game_dir)
        and not list_game_archives(game_dir)
        and not list_game_compiled_files(game_dir)
    ):
        raise ValueError("Aucun fichier .rpy/.rpym/.rpa/.rpyc/.rpyb/.rpymc trouvé dans 'game/'.")

    return RenpyProject(root=root, game_dir=game_dir)


def _excluded(p: Path) -> bool:
    return "tl" in set(p.parts)


def list_game_rpy_files(game_dir: str | Path) -> list[Path]:
    """
    Return source script files.

    We include both:
    - *.rpy
    - *.rpym (Ren'Py modules, often contain strings/dialogue too)
    """
    game_dir = Path(game_dir)
    files = [p for p in game_dir.rglob("*.rpy")] + [p for p in game_dir.rglob("*.rpym")]
    files = [p for p in files if not _excluded(p)]
    return sorted(files, key=lambda p: str(p).lower())


def list_game_archives(game_dir: str | Path) -> list[Path]:
    """List .rpa archives inside the game's directory tree."""
    game_dir = Path(game_dir)
    files = [p for p in game_dir.rglob("*.rpa")]
    files = [p for p in files if not _excluded(p)]
    return sorted(files, key=lambda p: str(p).lower())


def list_game_compiled_files(game_dir: str | Path) -> list[Path]:
    """
    Return compiled script files.

    Depending on build/engine version, scripts can be:
    - *.rpyc
    - *.rpyb
    - *.rpymc
    """
    game_dir = Path(game_dir)
    files = (
        [p for p in game_dir.rglob("*.rpyc")]
        + [p for p in game_dir.rglob("*.rpyb")]
        + [p for p in game_dir.rglob("*.rpymc")]
    )
    files = [p for p in files if not _excluded(p)]
    return sorted(files, key=lambda p: str(p).lower())