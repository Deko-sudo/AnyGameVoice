"""Backup helper.

Original game files are never overwritten without a restorable backup.
Backups live next to the original: <name>.<timestamp>.bak
"""

import os
import shutil
import time

__all__ = ["backup_file", "restore_file"]


def backup_file(path: str) -> str:
    """Copy path to a timestamped .bak sibling. Returns backup path."""
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = f"{path}.{stamp}.bak"
    shutil.copy2(path, backup)
    return backup


def restore_file(backup: str, original: str = "") -> str:
    """Restore a backup over the original. Returns original path."""
    if not backup or not os.path.isfile(backup):
        raise FileNotFoundError(f"Backup not found: {backup}")
    target = original or backup.rsplit(".bak", 1)[0].rsplit(".", 1)[0]
    # backup format is "<orig>.<stamp>.bak" -> strip last two suffixes
    if backup.endswith(".bak"):
        base = backup[: -len(".bak")]
        # remove .YYYYmmdd-HHMMSS
        import re

        base = re.sub(r"\.\d{8}-\d{6}$", "", base)
        target = original or base
    shutil.copy2(backup, target)
    return target
