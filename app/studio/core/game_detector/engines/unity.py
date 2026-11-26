"""Unity support (unpacking included).

- detection (see detector.py markers)
- audio asset inventory for the replacer
- audio extraction from bundles:
    1. UnityPy, if installed (proper AudioClip decode);
    2. fallback: magic-byte carving (WAV/Ogg/FSB5) from
       .assets/.bundle/.resource files — no extra deps.

Text extraction from compiled assets: not implemented (returns []).
"""

import os
import tempfile
from pathlib import Path

from app.utils.audio_utils import carve_embedded_audio

__all__ = [
    "list_audio_assets",
    "extract_unity_folder",
    "extract_unity_audio",
    "extract_unitypy_audio",
    "is_unitypy_available",
]

AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3"}
BUNDLE_SUFFIXES = {".assets", ".bundle", ".resource"}


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


def is_unitypy_available() -> bool:
    """True if UnityPy is importable."""
    try:
        import UnityPy  # noqa: F401

        return True
    except ImportError:
        return False


def extract_unitypy_audio(container: str, out_dir: str) -> list[str]:
    """Extract AudioClips via UnityPy. Raises RuntimeError if unavailable."""
    try:
        import UnityPy
    except ImportError as exc:
        raise RuntimeError("UnityPy not installed. Run: pip install UnityPy") from exc
    os.makedirs(out_dir, exist_ok=True)
    written: list[str] = []
    env = UnityPy.load(container)
    for obj in env.objects:
        if getattr(obj.type, "name", "") != "AudioClip":
            continue
        try:
            clip = obj.read()
            samples = getattr(clip, "samples", None)
            if not samples:
                continue
            # UnityPy returns {sample filename: encoded audio bytes}. Names come
            # from the bundle, so use them only to select a known extension.
            for name, data in samples.items():
                suffix = Path(name).suffix.lower()
                if suffix not in {".wav", ".ogg", ".m4a"} or not isinstance(data, bytes):
                    continue
                fd, dest = tempfile.mkstemp(prefix="clip-", suffix=suffix, dir=out_dir)
                try:
                    with os.fdopen(fd, "wb") as output:
                        output.write(data)
                except Exception:
                    os.unlink(dest)
                    raise
                written.append(dest)
        except Exception:
            continue  # one bad clip must not kill the whole container
    return written


def extract_unity_audio(game_path: str, out_dir: str) -> dict:
    """Extract audio from all Unity containers.

    Returns {"unitypy": [...], "carved": [...]}. Per-file strategy:
    UnityPy first (if installed), carving fallback on any failure.
    """
    game_root = Path(game_path).resolve()
    output_root = Path(out_dir).resolve()
    if output_root == game_root or game_root in output_root.parents:
        raise ValueError("Unity extraction output must be outside the game directory")
    os.makedirs(output_root, exist_ok=True)
    result: dict = {"unitypy": [], "carved": []}
    for fp in Path(game_path).rglob("*"):
        if fp.is_symlink() or not fp.is_file() or fp.suffix.lower() not in BUNDLE_SUFFIXES:
            continue
        # A fresh private directory prevents collisions between identically named
        # containers and keeps the fallback carver away from existing files.
        dest_dir = tempfile.mkdtemp(prefix="unity-", dir=output_root)
        got: list[str] = []
        if is_unitypy_available():
            try:
                got = extract_unitypy_audio(str(fp), dest_dir)
            except Exception:
                got = []
        result["unitypy"].extend(got)
        if not got:
            try:
                with open(fp, "rb") as fh:
                    data = fh.read()
                result["carved"].extend(carve_embedded_audio(data, dest_dir, prefix="audio"))
            except OSError:
                continue
    return result
