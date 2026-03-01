"""Ren'Py Translator - Rewrite .rpy scripts with translated strings.

Given extracted strings + translations, this module can:
- Rewrite the original .rpy files (optionally creating backups)
- Restore from backups if needed

Rewriting uses line-based heuristics (not an AST), so we take care to preserve
indentation and only replace the specific quoted segments that were extracted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict
import re


_RE_MENU_START = re.compile(r'^\s*menu\b.*:\s*$')
_RE_COMMENT_ONLY = re.compile(r'^\s*#')
_RE_TRANSLATE_BLOCK = re.compile(r'^(\s*)translate\s+\w+\s+.*:\s*$')
_RE_HEX_COLOR = re.compile(r"^#?[0-9a-fA-F]{3}([0-9a-fA-F]{1})?$|^#?[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")


# Block starters that are NOT dialogue and must NEVER be rewritten inside
TECHNICAL_BLOCK_KEYWORDS = {
    "style",
    "screen",
    "transform",
    "init",
    "python",
    "translate",
}

# Non-block technical single-line statements we still shouldn't rewrite directly
TECHNICAL_SINGLE_KEYWORDS = {
    "define",
    "default",
    "key",
    "image",
}

# Ren'Py statements that can contain quoted strings but are NOT dialogue
REN_PY_NON_DIALOGUE_STATEMENTS = {
    "scene", "show", "hide",
    "play", "stop", "queue", "voice",
    "with",
    "jump", "call", "return",
    "label",
    "pause", "window",
    "$",
}


def _indent_len(s: str) -> int:
    n = 0
    for ch in s:
        if ch == ' ':  # noqa: E271
            n += 1
        elif ch == '\t':
            n += 4
        else:
            break
    return n


def _find_first_quoted(text_line: str) -> tuple[int, int, str] | None:
    """Find first "..." respecting escapes (\" and \\)."""
    s = text_line
    i = 0
    n = len(s)
    while i < n:
        if s[i] == '"':
            start = i
            i += 1
            buf: list[str] = []
            escaped = False
            while i < n:
                ch = s[i]
                if escaped:
                    buf.append(ch)
                    escaped = False
                else:
                    if ch == "\\":
                        escaped = True
                    elif ch == '"':
                        end = i
                        return (start, end, "".join(buf))
                    else:
                        buf.append(ch)
                i += 1
            return None
        i += 1
    return None


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def rewrite_rpy_file(file_path: Path, translations: Dict[str, str]) -> bool:
    """Rewrite ONLY user-visible strings:

    - dialogue: e "text" / e happy "text" / narrator "text" / centered "text" / extend "text"
    - narration: "text"
    - menu choices: "text": ...

    Never rewrite inside screen/style/python/translate/init/transform blocks, and never
    rewrite Ren'Py statements like scene/show/play/voice...

    Returns True if modified.
    """

    original_lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    new_lines: list[str] = []
    modified = False

    in_menu = False
    menu_indent = 0

    in_translate_block = False
    translate_indent = 0

    in_technical_block = False
    technical_indent = 0

    for line in original_lines:
        stripped = line.strip()

        if not stripped:
            new_lines.append(line)
            continue

        if _RE_COMMENT_ONLY.match(stripped):
            new_lines.append(line)
            continue

        # Skip translate blocks entirely
        m_tr = _RE_TRANSLATE_BLOCK.match(line)
        if m_tr:
            in_translate_block = True
            translate_indent = _indent_len(m_tr.group(1))
            new_lines.append(line)
            continue
        if in_translate_block:
            if _indent_len(line) <= translate_indent and not line.lstrip().startswith('#'):
                in_translate_block = False
            new_lines.append(line)
            continue

        # Technical block start
        first_word = stripped.split(" ", 1)[0].rstrip(":") if stripped else ""
        if stripped.endswith(":") and first_word in TECHNICAL_BLOCK_KEYWORDS:
            in_technical_block = True
            technical_indent = _indent_len(line)
            in_menu = False
            new_lines.append(line)
            continue
        if in_technical_block:
            if _indent_len(line) <= technical_indent and not line.lstrip().startswith('#'):
                in_technical_block = False
            new_lines.append(line)
            continue

        # Menu start
        if _RE_MENU_START.match(line):
            in_menu = True
            menu_indent = _indent_len(line)
            new_lines.append(line)
            continue

        if in_menu:
            # exit menu if indentation is lost
            if _indent_len(line) <= menu_indent and not line.lstrip().startswith('#'):
                in_menu = False
                # fallthrough to handle this line normally
            else:
                q = _find_first_quoted(line)
                if not q:
                    new_lines.append(line)
                    continue

                start, end, text = q
                if _RE_HEX_COLOR.match(text.strip()):
                    new_lines.append(line)
                    continue
                if line.lstrip().startswith('"') and ":" in line[end + 1:]:
                    if text in translations:
                        translated = _escape(translations[text])
                        new_lines.append(line[:start + 1] + translated + line[end:])
                        modified = True
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
                continue

        # Single-line technical statements that must not be touched
        if first_word in TECHNICAL_SINGLE_KEYWORDS or first_word in TECHNICAL_BLOCK_KEYWORDS:
            new_lines.append(line)
            continue

        q = _find_first_quoted(line)
        if not q:
            new_lines.append(line)
            continue

        start, end, text = q
        if text not in translations:
            new_lines.append(line)
            continue

        prefix = line[:start].strip()
        first_tok = prefix.split(" ", 1)[0] if prefix else ""

        # Avoid Ren'Py translation old/new lines
        if first_tok in {"old", "new"}:
            new_lines.append(line)
            continue

        # If it's not narration (prefix isn't empty), ensure it's a say line, not a Ren'Py statement
        if prefix:
            if first_tok in REN_PY_NON_DIALOGUE_STATEMENTS:
                new_lines.append(line)
                continue
            if first_tok in TECHNICAL_SINGLE_KEYWORDS or first_tok in TECHNICAL_BLOCK_KEYWORDS:
                new_lines.append(line)
                continue

        translated = _escape(translations[text])
        new_lines.append(line[:start + 1] + translated + line[end:])
        modified = True

    if modified:
        file_path.write_text("\n".join(new_lines), encoding="utf-8")

    return modified


def backup_rpy_file(file_path: Path):
    """Create a backup copy of a .rpy file before rewriting."""
    bak = file_path.with_suffix(file_path.suffix + ".bak")
    if not bak.exists():
        bak.write_text(
            file_path.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )


def restore_rpy_file(file_path: Path):
    """Restore a .rpy file from a previously created backup."""
    bak = file_path.with_suffix(file_path.suffix + ".bak")
    if bak.exists():
        file_path.write_text(
            bak.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )
