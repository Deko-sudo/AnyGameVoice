"""Godot dialogue extraction.

Supports Dialogue Manager *.dialogue files:
  ~ title            -> section marker (skipped)
  Alice: Hello!      -> speaker + text
  - plain narration  -> narrator line (choices start with '- '? no:
                        choices use '- ' prefix too, so only top-level
                        'Name: text' and bare text lines are taken)

Also lists audio assets for the replacer.
"""

import os
from pathlib import Path

from app.core.extractor.models import ExtractedLine

__all__ = ["extract_godot_folder", "extract_godot_file", "list_audio_assets"]

AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3"}


def extract_godot_file(path: str) -> list[ExtractedLine]:
    """Extract dialogue from a single .dialogue file."""
    out: list[ExtractedLine] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for no, raw in enumerate(fh, 1):
                line = raw.strip()
                if not line or line.startswith(("~", "#", "=>", "do ", "set ", "if ", "elif ", "else", "while ", "for ", "match ")):
                    continue
                if line.startswith("- "):  # choice option, not spoken line
                    continue
                if ":" in line:
                    speaker, _, text = line.partition(":")
                    speaker, text = speaker.strip(), text.strip()
                    if speaker and text and " " not in speaker and len(speaker) <= 32:
                        out.append(
                            ExtractedLine(
                                speaker=speaker, text=text,
                                source_file=os.path.basename(path), line_no=no,
                            )
                        )
                        continue
                # bare narration line
                if len(line) > 1:
                    out.append(
                        ExtractedLine(
                            speaker="narrator", text=line,
                            source_file=os.path.basename(path), line_no=no,
                        )
                    )
    except OSError:
        return []
    return out


def extract_godot_folder(game_path: str) -> list[ExtractedLine]:
    """Extract dialogue from all .dialogue files under game_path."""
    lines: list[ExtractedLine] = []
    for fp in sorted(Path(game_path).rglob("*.dialogue")):
        if fp.is_file():
            lines.extend(extract_godot_file(str(fp)))
    return lines


def list_audio_assets(game_path: str, limit: int = 200) -> list[str]:
    """List audio asset paths (for the replacer)."""
    found: list[str] = []
    for fp in Path(game_path).rglob("*"):
        if len(found) >= limit:
            break
        if fp.is_file() and fp.suffix.lower() in AUDIO_SUFFIXES:
            found.append(os.path.relpath(fp, game_path))
    return sorted(found)
