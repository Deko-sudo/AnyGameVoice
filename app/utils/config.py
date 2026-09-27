"""App config (Phase 3).

Local-only JSON config. Privacy rights implemented here:
  show_data()   -> Settings -> Privacy -> Show Data
  delete_data() -> Settings -> Privacy -> Delete Data

Location: ~/.anygamevoice/config.json
Override for tests: ANYGAMEVOICE_HOME env var.
"""

import json
import os
from pathlib import Path

__all__ = [
    "Config",
    "get_config_path",
    "load_config",
    "save_config",
    "show_data",
    "delete_data",
]


def get_config_path() -> Path:
    """Path to the local config file."""
    base = os.environ.get("ANYGAMEVOICE_HOME") or os.path.expanduser("~/.anygamevoice")
    return Path(base) / "config.json"


class Config:
    """App config (local dict + hardware scan cache)."""

    def __init__(self, data: dict | None = None) -> None:
        self.data: dict = dict(data or {})

    @classmethod
    def load(cls) -> "Config":
        """Load from disk (empty if missing)."""
        return cls(load_config())

    def save(self) -> Path:
        """Persist to disk. Returns path."""
        return save_config(self.data)

    def set_hardware(self, hardware: dict, recommend: dict | None = None) -> None:
        """Cache a hardware scan (only called with user permission)."""
        self.data["hardware"] = hardware
        if recommend is not None:
            self.data["recommend"] = recommend

    def get(self, key: str, default=None):
        """Get a config value."""
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        """Set a config value (in memory; call save() to persist)."""
        self.data[key] = value


def load_config() -> dict:
    """Load config dict from disk ({} if missing/corrupt)."""
    path = get_config_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(data: dict) -> Path:
    """Write config dict to disk. Returns path."""
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return path


def show_data() -> dict:
    """Return all locally stored data (Privacy -> Show Data)."""
    return load_config()


def delete_data() -> bool:
    """Delete all locally stored scan data. Returns True if file removed."""
    path = get_config_path()
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False
