"""Backup helper.

Original game files are never overwritten without a restorable backup.
Backups live next to the original: <name>.<timestamp>.bak
"""

import logging
import os
import re
import shutil
import time
from pathlib import Path

__all__ = ["backup_file", "restore_file"]

logger = logging.getLogger(__name__)


def backup_file(path: str, *, destination: str | Path | None = None) -> str:
    """Copy path to a backup, defaulting to a timestamped sibling."""
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")
    if destination is None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        destination = f"{path}.{stamp}.bak"
    backup = os.fspath(destination)
    shutil.copy2(path, backup)
    return backup


def _original_path(backup: str) -> str:
    name = os.fspath(backup)
    if name.endswith(".bak"):
        return re.sub(r"\.\d{8}-\d{6}$", "", name[:-4])
    return name.rsplit(".bak", 1)[0].rsplit(".", 1)[0]


def restore_file(backup: str, original: str = "", *, remove_backup: bool = True) -> str:
    """Restore the original. A missing backup raises FileNotFoundError; cleanup errors are logged."""
    if not backup or not os.path.isfile(backup):
        raise FileNotFoundError(f"Backup not found: {backup}")
    target = original or _original_path(backup)
    if os.path.isdir(target):
        raise IsADirectoryError(target)
    if os.path.exists(target) and os.path.samefile(backup, target):
        raise shutil.SameFileError(f"Backup and target are the same file: {target}")
    shutil.copy2(backup, target)
    if remove_backup:
        _remove_backup(backup, target)
    return target


def _remove_backup(backup: str | Path, target: str | Path) -> None:
    try:
        os.unlink(backup)
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("Restored %s, but could not remove backup %s: %s", target, backup, exc)
