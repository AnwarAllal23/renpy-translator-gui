"""Ren'Py Translator - High-level extraction API.

This module provides a small, stable surface used by the UI:
- extract_strings(): read .rpy files and return extracted translatable strings
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.project_scanner import list_game_rpy_files
from core.rpy_parser import ExtractedString, parse_rpy_file


@dataclass
class ExtractionResult:
    """Result object returned by extract_strings()."""
    items: list[ExtractedString]
    total_files: int


def extract_strings(game_dir: Path) -> ExtractionResult:
    """Extract translatable strings from a list of .rpy files."""
    files = list_game_rpy_files(game_dir)
    all_items: list[ExtractedString] = []

    for f in files:
        all_items.extend(parse_rpy_file(f, rel_from=game_dir))

    return ExtractionResult(items=all_items, total_files=len(files))
