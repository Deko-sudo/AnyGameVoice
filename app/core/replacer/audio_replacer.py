"""Audio replacer.

Replaces a game audio file with generated audio, keeping a backup.
"""

import logging
import os
import shutil
from pathlib import Path

from .backup import _original_path, backup_file, restore_file

__all__ = ["replace_audio", "uninstall_audio"]

logger = logging.getLogger(__name__)

AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3"}


def replace_audio(target: str, source: str, make_backup: bool = True) -> str:
    """Replace target audio with source file.

    Returns backup path (or "" if make_backup is False).
    Raises FileNotFoundError / ValueError on bad input.
    """
    if not target or not os.path.isfile(target):
        raise FileNotFoundError(f"Target not found: {target}")
    if not source or not os.path.isfile(source):
        raise FileNotFoundError(f"Source not found: {source}")
    if os.path.splitext(target)[1].lower() not in AUDIO_SUFFIXES:
        raise ValueError(f"Unsupported target audio format: {target}")
    backup = backup_file(target) if make_backup else ""
    shutil.copy2(source, target)
    return backup


def uninstall_audio(target: str, backup: str) -> bool:
    """Restore one target from its replace_audio backup. Log failures and return False."""
    try:
        if not backup or not os.path.isfile(backup):
            raise FileNotFoundError(f"Backup not found: {backup}")
        if not target or Path(target).resolve() != Path(_original_path(backup)).resolve():
            raise ValueError("Backup belongs to a different target")
        restore_file(backup)
    except Exception as exc:  # This entry point reports restore failures through its boolean result.
        logger.error("Could not uninstall audio %s using %s: %s", target, backup, exc)
        return False
    return True
