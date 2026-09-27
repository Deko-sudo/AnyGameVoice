"""Permission helpers.

Explicit opt-in checks before touching user files.
"""

import os

__all__ = ["request_permission", "check_path_access"]


def request_permission(name: str) -> bool:
    """Stub permission request.

    Real UI will ask the user; for now auto-approve known safe scans.
    """
    return name in {"hardware_scan", "game_folder_scan"}


def check_path_access(path: str) -> dict:
    """Check read/write access for a game folder."""
    result = {"path": path, "exists": False, "readable": False, "writable": False}
    if not path or not os.path.exists(path):
        return result
    result["exists"] = True
    result["readable"] = os.access(path, os.R_OK)
    result["writable"] = os.access(path, os.W_OK)
    return result
