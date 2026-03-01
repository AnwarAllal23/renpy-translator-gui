"""Ren'Py Translator - Helpers for packaged (compiled) Ren'Py games.

Packaged games often ship with:
- .rpa archives (assets/scripts)
- .rpyc compiled script files

This module prepares a *workspace* copy of the game where scripts can be
decompiled (when possible) so the translator can operate on .rpy sources.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import shutil
import subprocess
import sys
from typing import Callable

from core.rpa_extractor import extract_rpa3, RPAExtractError


class PackagedPrepError(RuntimeError):
    """Raised when preparing a packaged-game workspace fails."""
    pass


@dataclass
class PackagedPrepResult:
    """Result of preparing a packaged-game workspace."""
    workspace_root: Path
    game_dir: Path
    rpa_found: int
    rpyc_found: int
    rpy_found_after: int
    decompile_failed: int


def _default_workspace_dir(game_dir: Path) -> Path:
    home = Path.home()
    base = home / ".renpy_translator_workspace"
    h = hashlib.sha1(str(game_dir).encode("utf-8")).hexdigest()[:10]
    return base / f"{game_dir.parent.name}_{h}"


def _looks_like_python_exe(exe_path: str) -> bool:
    p = exe_path.lower().replace("\\", "/")
    return p.endswith("/python.exe") or p.endswith("/pythonw.exe") or p.endswith("/python")


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
        )
        out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        return p.returncode, out.strip()
    except FileNotFoundError as e:
        return 127, str(e)


def _run_rpycdec(args: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    candidates: list[list[str]] = []

    if _looks_like_python_exe(sys.executable):
        candidates.append([sys.executable, "-m", "rpycdec", *args])

    candidates.append(["py", "-m", "rpycdec", *args])
    candidates.append(["python", "-m", "rpycdec", *args])
    candidates.append(["rpycdec", *args])

    errors: list[str] = []
    for cmd in candidates:
        code, out = _run(cmd, cwd=cwd)
        if code == 0:
            return True, out
        errors.append(f"cmd={' '.join(cmd)}\n{out}")

    return False, "\n\n".join(errors[:4])


def _normalize_selected_path(p: Path) -> Path:
    p = p.expanduser().resolve()
    if (p / "game").is_dir():
        return p / "game"
    return p


def _excluded(p: Path) -> bool:
    return "tl" in set(p.parts)


def _count_packaged_assets(game_dir: Path) -> tuple[int, int]:
    rpa_found = sum(1 for _ in game_dir.rglob("*.rpa"))
    compiled_found = (
        sum(1 for _ in game_dir.rglob("*.rpyc"))
        + sum(1 for _ in game_dir.rglob("*.rpyb"))
        + sum(1 for _ in game_dir.rglob("*.rpymc"))
    )
    return rpa_found, compiled_found


def _list_compiled(ws_game: Path) -> list[Path]:
    files = (
        list(ws_game.rglob("*.rpyc"))
        + list(ws_game.rglob("*.rpyb"))
        + list(ws_game.rglob("*.rpymc"))
    )
    files = [p for p in files if not _excluded(p)]
    return sorted(files, key=lambda p: str(p).lower())


def _count_files(root: Path) -> int:
    return sum(1 for p in root.rglob("*") if p.is_file())


def prepare_packaged_game(selected_path: Path, log_cb: Callable[[str], None] | None = None) -> PackagedPrepResult:
    game_dir = _normalize_selected_path(Path(selected_path))
    if not game_dir.exists() or not game_dir.is_dir():
        raise PackagedPrepError("game_dir invalide.")

    def log(m: str) -> None:
        if log_cb:
            log_cb(m)

    rpa_found, compiled_found = _count_packaged_assets(game_dir)
    if rpa_found == 0 and compiled_found == 0:
        raise PackagedPrepError("Ce jeu ne semble pas packagé (aucun .rpa/.rpyc/.rpyb/.rpymc trouvé).")

    workspace_root = _default_workspace_dir(game_dir)
    ws_game = workspace_root / "game"

    log(f"📁 Workspace: {workspace_root}")
    workspace_root.mkdir(parents=True, exist_ok=True)

    if ws_game.exists():
        log("🧹 Cleaning previous workspace/game …")
        shutil.rmtree(ws_game, ignore_errors=True)

    log("📋 Copying game/ to workspace …")
    shutil.copytree(game_dir, ws_game)

    # 1) Extract .rpa (guaranteed): try rpycdec, fallback to our extractor if nothing extracted
    ws_rpas = [p for p in ws_game.rglob("*.rpa") if not _excluded(p)]
    if ws_rpas:
        log(f"🧩 Found {len(ws_rpas)} .rpa archives. Extracting …")
        for rpa in ws_rpas:
            before = _count_files(ws_game)
            log(f"   • Extracting {rpa.name} (rpycdec unrpa)…")
            ok, out = _run_rpycdec(["unrpa", str(rpa)], cwd=ws_game)
            after = _count_files(ws_game)

            if (not ok) or (after <= before):
                log(f"⚠️ rpycdec unrpa produced no files for {rpa.name}. Using built-in RPA extractor…")
                try:
                    extracted = extract_rpa3(rpa, ws_game)
                    log(f"✅ Extracted {len(extracted)} files from {rpa.name} (fallback).")
                except RPAExtractError as e:
                    raise PackagedPrepError(f"Échec extraction de {rpa.name}: {e}")
    else:
        log("🧩 No .rpa archives found in workspace.")

    # 2) Decompile compiled scripts (best-effort, per-file)
    compiled_files = _list_compiled(ws_game)
    failed = 0

    if compiled_files:
        log(f"🧾 Decompiling {len(compiled_files)} compiled scripts (per-file, continue on errors)…")
        for f in compiled_files:
            ok, out = _run_rpycdec(["decompile", str(f)], cwd=ws_game)
            if not ok:
                failed += 1
                log(f"⚠️ Decompile failed: {f.relative_to(ws_game)}")
        log(f"✅ Decompile finished. Failed files: {failed}")
    else:
        log("ℹ️ No compiled scripts found to decompile.")

    rpy_found_after = sum(1 for _ in ws_game.rglob("*.rpy"))
    log(f"✅ Done. .rpy files available: {rpy_found_after}")

    if rpy_found_after == 0:
        raise PackagedPrepError(
            "Aucun .rpy n'a pu être généré après extraction/décompilation.\n"
            "Dans ce cas, le jeu est probablement incompatible avec la décompilation."
        )

    return PackagedPrepResult(
        workspace_root=workspace_root,
        game_dir=ws_game,
        rpa_found=rpa_found,
        rpyc_found=compiled_found,
        rpy_found_after=rpy_found_after,
        decompile_failed=failed,
    )