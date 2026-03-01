"""Ren'Py Translator - Parse .rpy scripts and extract translatable strings.

The parser is conservative:
- It tries to detect quoted strings on lines that *look* like dialogue/strings
- It preserves enough context (file/line) to support later rewriting

This module avoids full Ren'Py AST parsing; it is built to be robust across
different projects while remaining easy to maintain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class ExtractedString:
    """Represents a translatable string found in a .rpy file."""
    kind: str            # "dialogue" | "narration" | "menu" | "ui"
    text: str
    file: str
    line: int
    speaker: str | None
    context: str

TECHNICAL_BLOCK_KEYWORDS = {
    "style",
    "define",
    "transform",
    "init",
    "default",
    "key",
    "image",
    "python",
    "translate",
}

REN_PY_NON_DIALOGUE_STATEMENTS = {
    "scene",
    "show",
    "hide",
    "play",
    "stop",
    "queue",
    "voice",
    "with",
    "jump",
    "call",
    "return",
    "label",
    "pause",
    "window",
}

_RE_MENU_START = re.compile(r'^\s*menu\b.*:\s*$')
_RE_COMMENT_ONLY = re.compile(r'^\s*#')
_RE_TRANSLATE_BLOCK = re.compile(r'^(\s*)translate\s+\w+\s+.*:\s*$')
_RE_HEX_COLOR = re.compile(r"^#?[0-9a-fA-F]{3}([0-9a-fA-F]{1})?$|^#?[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")

_RE_SAY_LINE = re.compile(
    r'^(\s*)([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(?:\s+[^\s"]+)*\s*"'
)

_RE_SCREEN_START = re.compile(r'^\s*screen\s+([A-Za-z_]\w*)\b.*:\s*$')

_RE_UI_LINE = re.compile(r'^\s*(textbutton|text|label|tooltip)\s+"')


def _indent_len(s: str) -> int:
    n = 0
    for ch in s:
        if ch == ' ':
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


def _looks_translatable(s: str) -> bool:
    t = s.strip()
    if not t:
        return False

    # Avoid color strings
    if _RE_HEX_COLOR.match(t):
        return False

    # Avoid punctuation-only
    if all(ch in ".!?…,-:; " for ch in t):
        return False

    # Avoid pure identifiers
    if t.isidentifier():
        return False

    # Avoid pure interpolation strings like "[page]" or "[config.version]"
    if t.startswith("[") and t.endswith("]"):
        return False

    return True


def parse_rpy_file(file_path: Path, rel_from: Path) -> list[ExtractedString]:
    """
    Extract user-visible strings:
    - dialogue: speaker "..."
    - narration: "..."
    - menu choices: menu: "Choice":
    - ui: text/textbutton/label/tooltip "..." inside screen blocks

    Still avoids python/style/translate blocks, and avoids technical statements.
    """
    rel = str(file_path.relative_to(rel_from)).replace("\\", "/")
    content = file_path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()

    results: list[ExtractedString] = []

    in_menu = False
    menu_indent = 0

    in_translate_block = False
    translate_indent = 0

    in_technical_block = False
    technical_indent = 0

    in_screen = False
    screen_indent = 0

    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()

        if not stripped:
            continue
        if _RE_COMMENT_ONLY.match(stripped):
            continue

        # translate blocks (already translations) => skip entirely
        m_tr = _RE_TRANSLATE_BLOCK.match(line)
        if m_tr:
            in_translate_block = True
            translate_indent = _indent_len(m_tr.group(1))
            continue
        if in_translate_block:
            if _indent_len(line) <= translate_indent and not line.lstrip().startswith('#'):
                in_translate_block = False
            else:
                continue

        # Screen start/end tracking
        m_sc = _RE_SCREEN_START.match(line)
        if m_sc:
            in_screen = True
            screen_indent = _indent_len(line)
            continue
        if in_screen:
            # exit screen when indent returns to <= screen_indent
            if _indent_len(line) <= screen_indent and not line.lstrip().startswith('#'):
                in_screen = False
            else:
                # Only extract safe UI strings inside screens
                if _RE_UI_LINE.match(line):
                    q = _find_first_quoted(line)
                    if q:
                        _start, _end, text = q
                        if _looks_translatable(text):
                            results.append(ExtractedString(
                                kind="ui",
                                text=text,
                                file=rel,
                                line=idx,
                                speaker=None,
                                context='screen ui: text/textbutton/label/tooltip "..."'
                            ))
                continue

        # Technical block start?
        first_word = stripped.split(" ", 1)[0].rstrip(":")
        if stripped.endswith(":") and first_word in TECHNICAL_BLOCK_KEYWORDS:
            in_technical_block = True
            technical_indent = _indent_len(line)
            continue
        if in_technical_block:
            if _indent_len(line) <= technical_indent and not line.lstrip().startswith('#'):
                in_technical_block = False
            else:
                continue

        # Menu start
        if _RE_MENU_START.match(line):
            in_menu = True
            menu_indent = _indent_len(line)
            continue

        if in_menu:
            if _indent_len(line) <= menu_indent and not line.lstrip().startswith('#'):
                in_menu = False
            else:
                # First check if it's a menu choice (starts with " and ends with :)
                q = _find_first_quoted(line)
                if q:
                    _start, end, text = q
                    after = line[end + 1:]
                    if ':' in after and line.lstrip().startswith('"') and _looks_translatable(text):
                        results.append(ExtractedString(
                            kind="menu",
                            text=text,
                            file=rel,
                            line=idx,
                            speaker=None,
                            context='menu "...":'
                        ))
                        continue
                    # ALSO extract dialogue/narration inside menus
                    # Check if this looks like a dialogue (speaker "text") or narration ("text")
                    if line.lstrip().startswith('"'):
                        # Narration inside menu
                        if _looks_translatable(text):
                            results.append(ExtractedString(
                                kind="narration",
                                text=text,
                                file=rel,
                                line=idx,
                                speaker=None,
                                context='menu narration "..."'
                            ))
                    else:
                        # Dialogue inside menu (e.g., hinata.c "text")
                        m_say = _RE_SAY_LINE.match(line)
                        if m_say:
                            _indent, speaker = m_say.groups()
                            speaker_root = speaker.split(".", 1)[0]
                            if speaker_root not in REN_PY_NON_DIALOGUE_STATEMENTS and speaker_root not in TECHNICAL_BLOCK_KEYWORDS:
                                if _looks_translatable(text):
                                    results.append(ExtractedString(
                                        kind="dialogue",
                                        text=text,
                                        file=rel,
                                        line=idx,
                                        speaker=speaker,
                                        context=f'menu {speaker} "..."'
                                    ))
                continue

        # Skip python one-liners
        if stripped.startswith('$'):
            continue

        # Dialogue speaker "..." (now supports dotted speakers)
        m_say = _RE_SAY_LINE.match(line)
        if m_say:
            _indent, speaker = m_say.groups()

            # ✅ IMPORTANT: use root speaker before dot for filters
            speaker_root = speaker.split(".", 1)[0]

            if speaker_root in REN_PY_NON_DIALOGUE_STATEMENTS:
                continue
            if speaker_root in TECHNICAL_BLOCK_KEYWORDS:
                continue
            if speaker_root in {"old", "new"}:
                continue

            q = _find_first_quoted(line)
            if not q:
                continue
            _start, _end, text = q
            if not _looks_translatable(text):
                continue

            results.append(ExtractedString(
                kind="dialogue",
                text=text,
                file=rel,
                line=idx,
                speaker=speaker,
                context=f'{speaker} "..."'
            ))
            continue

        # Narration "..." (line begins with quote after indentation)
        if line.lstrip().startswith('"'):
            q = _find_first_quoted(line)
            if not q:
                continue
            _start, _end, text = q
            if not _looks_translatable(text):
                continue
            results.append(ExtractedString(
                kind="narration",
                text=text,
                file=rel,
                line=idx,
                speaker=None,
                context='"..."'
            ))

    return results