"""Recoverable, per-game locks for manifest operations."""

import json
import logging
import os
import socket
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .manifest import _atomic_write, _utc_now

__all__ = ["game_lock", "lock_info"]

logger = logging.getLogger(__name__)


def lock_info(path: str | Path) -> dict | None:
    """Read the owner of a lock. Return None for absent or malformed metadata."""
    path = Path(path)
    try:
        if not path.is_file() or path.is_symlink():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        pid, started, host = data["pid"], data["started_at"], data["host"]
        if type(pid) is not int or pid <= 0 or not isinstance(host, str) or not host:
            return None
        if not isinstance(started, str):
            return None
        timestamp = started[:-1] + "+00:00" if started.endswith("Z") else started
        if datetime.fromisoformat(timestamp).utcoffset() is None:
            return None
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        return None
    return data


def _pid_alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, OverflowError):
            return False
        except PermissionError:
            return True
        return True

    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    if pid > 0xFFFFFFFF:
        return False
    handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER
            return False
        if error == 5:  # ERROR_ACCESS_DENIED
            return True
        raise ctypes.WinError(error)
    try:
        result = kernel.WaitForSingleObject(handle, 0)
        if result == 0:  # WAIT_OBJECT_0, process exited
            return False
        if result == 258:  # WAIT_TIMEOUT, process still running
            return True
        raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)


@contextmanager
def _lock_metadata(directory: Path):
    # Serialize check-and-replace and check-and-unlink across processes. The OS
    # releases this short-lived lock on exit, so the guard file can stay in place.
    with (directory / ".lock-guard").open("a+b") as guard:
        if os.name == "nt":
            import msvcrt

            guard.seek(0)
            msvcrt.locking(guard.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                guard.seek(0)
                msvcrt.locking(guard.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
            yield


@contextmanager
def game_lock(game: Path):
    """Hold exclusive access to one game's manifest operations."""
    if game == game.parent or game.name.lower() in (".agv-manifests", ".agv-backups"):
        raise ValueError(f"Invalid game directory: {game}")
    manifests = game.parent / ".agv-manifests"
    if manifests.is_symlink():
        raise ValueError(f"Mod storage cannot be a symlink: {manifests}")
    manifests.mkdir(mode=0o700, exist_ok=True)
    path = manifests / f".{game.name}.lock"
    owner = {"pid": os.getpid(), "started_at": _utc_now(), "host": socket.gethostname()}
    with _lock_metadata(manifests):
        current = lock_info(path)
        if current and current["host"] == owner["host"] and _pid_alive(current["pid"]):
            raise RuntimeError(
                f"install already running, pid={current['pid']}, started={current['started_at']}"
            )
        if path.exists() or path.is_symlink():
            if current and current["host"] == owner["host"]:
                logger.warning("Stale lock from dead process, taking over: %s", path)
            else:
                logger.warning("Stale lock from another host or invalid metadata, taking over: %s", path)
            if path.is_dir() and not path.is_symlink():
                path.rmdir()  # Empty lock directories from the earlier implementation.
        _atomic_write(path, json.dumps(owner, ensure_ascii=False) + "\n")
    try:
        yield manifests
    finally:
        with _lock_metadata(manifests):
            if owner["pid"] == os.getpid() and lock_info(path) == owner:
                path.unlink(missing_ok=True)
