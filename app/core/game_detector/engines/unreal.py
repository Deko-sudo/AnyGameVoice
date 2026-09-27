"""Unreal support (Phase 8, partial).

Full .pak parsing needs `unrealpak` and per-game AES keys.
What works now:
  - detection (see detector.py markers: *.uproject, *.pak)
  - audio asset inventory for the replacer (loose + containers)

Text extraction from .pak/.uasset: not implemented (returns []).
"""

import os
from pathlib import Path

__all__ = ["list_audio_assets", "extract_unreal_folder"]

AUDIO_SUFFIXES = {".wav", ".ogg", ".uasset", ".ubulk", ".pak"}


def list_audio_assets(game_path: str, limit: int = 200) -> list[str]:
    """List loose audio files + pak containers."""
    found: list[str] = []
    for fp in Path(game_path).rglob("*"):
        if len(found) >= limit:
            break
        if fp.is_file() and fp.suffix.lower() in AUDIO_SUFFIXES:
            found.append(os.path.relpath(fp, game_path))
    return sorted(found)


def extract_unreal_folder(game_path: str) -> list:
    """Unreal dialogue extraction: not implemented (needs unpacked assets)."""
    return []
