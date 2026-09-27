"""Voice preset manager.

Voices are .onnx/.wav/.pt files under voices/presets (shipped)
and voices/user (user-added). Nothing is uploaded anywhere.
"""

import os
from pathlib import Path

from app.models.voice import Voice
from app.utils.paths import preset_dir, user_voices_dir

PRESET_DIR = preset_dir()
USER_DIR = user_voices_dir()

VALID_SUFFIXES = {".onnx", ".wav", ".pt", ".pth", ".ckpt"}

__all__ = ["VoiceManager", "PRESET_DIR", "USER_DIR"]


class VoiceManager:
    """Manage voice presets (stub)."""

    def __init__(self, user_dir: str | Path = USER_DIR) -> None:
        self.user_dir = Path(user_dir)
        self.user_dir.mkdir(parents=True, exist_ok=True)

    def list_voices(self) -> list:
        """List voices from presets + user dirs as Voice objects."""
        voices: list[Voice] = []
        for directory, engine in ((PRESET_DIR, "preset"), (self.user_dir, "user")):
            if not directory.is_dir():
                continue
            for fp in sorted(directory.iterdir()):
                if fp.is_file() and fp.suffix.lower() in VALID_SUFFIXES:
                    voices.append(
                        Voice(name=fp.stem, path=str(fp), engine=engine)
                    )
        return voices

    def add_voice(self, src: str, name: str = "") -> Voice:
        """Copy a voice sample into the user dir."""
        import shutil

        src_p = Path(src)
        if not src_p.is_file():
            raise FileNotFoundError(f"Voice sample not found: {src}")
        dest = self.user_dir / (name or src_p.stem + src_p.suffix)
        if dest.suffix.lower() not in VALID_SUFFIXES:
            raise ValueError(f"Unsupported voice format: {dest.suffix}")
        shutil.copy2(src_p, dest)
        return Voice(name=dest.stem, path=str(dest), engine="user")

    def remove_voice(self, name: str) -> bool:
        """Delete a user voice by name. Returns True if removed."""
        for fp in self.user_dir.iterdir():
            if fp.is_file() and fp.stem == name:
                fp.unlink()
                return True
        return False
