"""Ren'Py Translator - Minimal RPA3 extractor.

Some packaged Ren'Py games store assets/scripts in .rpa archives. This module
implements a small RPA3 reader that can extract files into a destination folder.

Note: Ren'Py supports multiple RPA formats; this implementation targets RPA3.
"""

from __future__ import annotations

from pathlib import Path
import re
import struct
import pickle
import zlib
from typing import List, Tuple


class RPAExtractError(RuntimeError):
    """Raised when an RPA archive cannot be parsed or extracted."""
    pass


def _parse_rpa3_header(first_line: str) -> tuple[int, int]:
    """
    Header looks like:
      RPA-3.0 000000000034f7e4 42424242
    Returns: (index_offset, key)
    """
    m = re.match(r"RPA-3\.0\s+([0-9a-fA-F]{16})\s+([0-9a-fA-F]{8})", first_line.strip())
    if not m:
        raise RPAExtractError("Not an RPA-3.0 archive header.")
    return int(m.group(1), 16), int(m.group(2), 16)


def extract_rpa3(rpa_path: Path, out_dir: Path) -> List[Path]:
    """
    Extracts an RPA-3.0 archive to out_dir (preserving internal paths).
    Works for common RPA-3.0 format:
      - index at offset in header
      - index blob is xor'ed with key bytes (4 bytes), then zlib-compressed pickle
      - file offsets/lengths are xor'ed with key
    """
    if not rpa_path.exists():
        raise RPAExtractError(f"File not found: {rpa_path}")

    data = rpa_path.read_bytes()

    try:
        first_line = data.splitlines()[0].decode("utf-8", errors="ignore")
    except Exception as e:
        raise RPAExtractError(f"Failed to read header: {e}")

    index_offset, key = _parse_rpa3_header(first_line)

    if index_offset <= 0 or index_offset >= len(data):
        raise RPAExtractError("Invalid index offset in header.")

    blob = data[index_offset:]

    key_bytes = struct.pack(">I", key)
    xored = bytearray(blob)
    for i in range(len(xored)):
        xored[i] ^= key_bytes[i % 4]

    try:
        dec = zlib.decompress(bytes(xored))
    except Exception:
        try:
            dec = zlib.decompress(blob)
        except Exception as e:
            raise RPAExtractError(f"Failed to decompress index: {e}")

    try:
        index = pickle.loads(dec)
    except Exception as e:
        raise RPAExtractError(f"Failed to load pickle index: {e}")

    if not isinstance(index, dict):
        raise RPAExtractError("Index is not a dict.")

    extracted: List[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, entries in index.items():
        # entries is usually a list of tuples
        if not isinstance(entries, (list, tuple)):
            continue

        for entry in entries:
            if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                continue

            off = entry[0] ^ key
            length = entry[1] ^ key

            if off < 0 or length <= 0 or off + length > len(data):
                continue

            chunk = data[off : off + length]
            out_path = out_dir / str(name).replace("\\", "/")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(chunk)
            extracted.append(out_path)

    return extracted