"""Atomic replacement of local application-owned files."""

import json
import os
from pathlib import Path
import shutil
import tempfile


def atomic_copy(source: str | Path, target: str | Path) -> None:
    """Copy to a sibling temporary file, then replace the destination."""
    target = Path(target)
    fd, temp = tempfile.mkstemp(prefix=f'.{target.name}.', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as dst, open(source, 'rb') as src:
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
        shutil.copystat(source, temp)
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def atomic_json(target: str | Path, data: dict) -> None:
    """Persist a complete JSON document without exposing partial content."""
    target = Path(target)
    fd, temp = tempfile.mkstemp(prefix=f'.{target.name}.', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
