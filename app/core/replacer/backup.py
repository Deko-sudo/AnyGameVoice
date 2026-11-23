"""Backup helper.

Original game files are never overwritten without a restorable backup.
Backups live next to the original: <name>.<timestamp>.bak
"""

import logging
import os
import re
import shutil
import time

__all__ = ["backup_file", "restore_file"]

logger = logging.getLogger(__name__)


def backup_file(path: str) -> str:
    """Copy path to a timestamped .bak sibling. Returns backup path."""
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = f"{path}.{stamp}.bak"
    shutil.copy2(path, backup)
    return backup


def _original_path(backup: str) -> str:
    name = os.fspath(backup)
    if name.endswith(".bak"):
        return re.sub(r"\.\d{8}-\d{6}$", "", name[:-4])
    return name.rsplit(".bak", 1)[0].rsplit(".", 1)[0]


def restore_file(backup: str, original: str = "") -> str:
    """Restore the original. A missing backup raises FileNotFoundError; cleanup errors are logged."""
    if not backup or not os.path.isfile(backup):
        raise FileNotFoundError(f"Backup not found: {backup}")
    target = original or _original_path(backup)
    if os.path.isdir(target):
        raise IsADirectoryError(target)
    if os.path.exists(target) and os.path.samefile(backup, target):
        raise shutil.SameFileError(f"Backup and target are the same file: {target}")
    shutil.copy2(backup, target)
    try:
        os.unlink(backup)
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("Restored %s, but could not remove backup %s: %s", target, backup, exc)
    return target
