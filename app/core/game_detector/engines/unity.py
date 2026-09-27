"""Unity support (Phase 8, partial).

Full AssetBundle parsing needs the `UnityPy` package and is out of scope.
What works now:
  - detection (see detector.py markers)
  - audio asset inventory for the replacer (StreamingAssets + loose files)

Text extraction from compiled assets: not implemented (returns []).
"""

import os
from pathlib import Path

__all__ = ["list_audio_assets", "extract_unity_folder"]

AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3"}
BUNDLE_SUFFIXES = {".assets", ".bundle", ".resource", ".pak"}


def list_audio_assets(game_path: str, limit: int = 200) -> list[str]:
    """List loose audio files + bundle containers holding audio."""
    found: list[str] = []
    for fp in Path(game_path).rglob("*"):
        if len(found) >= limit:
            break
        if fp.is_file() and fp.suffix.lower() in AUDIO_SUFFIXES | BUNDLE_SUFFIXES:
            found.append(os.path.relpath(fp, game_path))
    return sorted(found)


def extract_unity_folder(game_path: str) -> list:
    """Unity dialogue extraction: not implemented (needs UnityPy)."""
    return []
