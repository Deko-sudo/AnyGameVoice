"""Audio replacer.

Replaces a game audio file with generated audio, keeping a backup.
"""

import os
import shutil

from .backup import backup_file

__all__ = ["replace_audio"]

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
