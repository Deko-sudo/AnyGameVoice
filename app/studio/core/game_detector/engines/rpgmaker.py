"""RPG Maker MV/MZ dialogue extraction.

Parses data/Map*.json (and data/CommonEvents.json):
  code 101 -> speaker setup (parameters[4] = name in MV, [0] fallback)
  code 401 -> dialogue text lines
  code 102 -> choices (also useful voice-over targets)

Null entries and missing keys are tolerated (real game files are messy).
"""

import json
import os
from pathlib import Path

from app.studio.core.extractor.models import ExtractedLine

__all__ = ["extract_rpgmaker_folder", "extract_rpgmaker_file"]

TEXT_CODES = {401, 102}


def _iter_event_lists(data) -> list:
    """Yield command lists from a Map file or CommonEvents file."""
    lists = []
    if isinstance(data, dict):  # Map file: {"events": [...]}
        for ev in data.get("events") or []:
            if not isinstance(ev, dict):
                continue
            for page in ev.get("pages") or []:
                if isinstance(page, dict) and isinstance(page.get("list"), list):
                    lists.append(page["list"])
    elif isinstance(data, list):  # CommonEvents.json: [{...}, null, ...]
        for ev in data:
            if isinstance(ev, dict) and isinstance(ev.get("list"), list):
                lists.append(ev["list"])
    return lists


def extract_rpgmaker_file(path: str) -> list[ExtractedLine]:
    """Extract dialogue from a single RPG Maker JSON file."""
    out: list[ExtractedLine] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    for commands in _iter_event_lists(data):
        speaker = ""
        for cmd in commands:
            if not isinstance(cmd, dict):
                continue
            code = cmd.get("code")
            params = cmd.get("parameters") or []
            if code == 101 and params:
                # MV: [face, index, bg, pos, name]; MZ may put name first
                name = params[4] if len(params) > 4 and params[4] else params[0]
                speaker = str(name) if isinstance(name, str) else ""
            elif code in TEXT_CODES and params:
                texts = params[0] if code == 102 and isinstance(params[0], list) else params
                texts = texts if code == 102 else [" ".join(p for p in params if isinstance(p, str))]
                for text in texts:
                    if not isinstance(text, str) or not text.strip():
                        continue
                    out.append(
                        ExtractedLine(
                            speaker=speaker or "narrator",
                            text=text.strip(),
                            source_file=os.path.basename(path),
                            line_no=0,
                        )
                    )
    return out


def extract_rpgmaker_folder(game_path: str) -> list[ExtractedLine]:
    """Extract dialogue from data/*.json (Map files + CommonEvents)."""
    root = Path(game_path)
    data_dirs = [d for d in (root / "data", root / "www" / "data", root)
                 if d.is_dir() and any(d.glob("Map[0-9]*.json"))]
    if not data_dirs:
        data_dirs = sorted({f.parent for f in root.rglob("Map[0-9]*.json")})
    files = []
    for directory in data_dirs:
        files.extend(directory.glob("Map[0-9]*.json"))
        if (directory / "CommonEvents.json").is_file():
            files.append(directory / "CommonEvents.json")
    lines: list[ExtractedLine] = []
    for fp in sorted(set(files)):
        if fp.is_file():
            extracted = extract_rpgmaker_file(str(fp))
            for line in extracted:
                line.source_file = fp.relative_to(root).as_posix()
                line.engine = "rpgmaker"
            lines.extend(extracted)
    return lines
