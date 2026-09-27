"""Filesystem locations (dev + PyInstaller bundle).

- Bundled data (ui/, voices/presets) lives in sys._MEIPASS in onefile mode.
- Writable user data always lives outside the bundle:
  ANYGAMEVOICE_HOME or ~/.anygamevoice (voices, config, model cache).
"""

import os
import sys
from pathlib import Path

__all__ = [
    "resource_path",
    "project_root",
    "preset_dir",
    "user_home",
    "user_voices_dir",
]


def resource_path(*parts: str) -> Path:
    """Path to a shipped resource (bundle-aware)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base, *parts)
    return project_root().joinpath(*parts)


def project_root() -> Path:
    """Repo root in dev (app/utils/paths.py -> up 3), bundle dir in prod."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parents[2]


def user_home() -> Path:
    """Writable per-user home (override with ANYGAMEVOICE_HOME)."""
    base = os.environ.get("ANYGAMEVOICE_HOME") or os.path.join(
        os.path.expanduser("~"), ".anygamevoice"
    )
    return Path(base)


def preset_dir() -> Path:
    """Shipped voice presets (read-only in bundle)."""
    return resource_path("voices", "presets")


def user_voices_dir() -> Path:
    """User-added voices (always writable)."""
    return user_home() / "voices"
