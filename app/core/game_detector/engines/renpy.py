"""Ren'Py dialogue extraction.

Parses .rpy script files with a conservative regex:
  [indent] speaker "text"
  [indent] "narration"
Comment lines (# ...) are skipped. Escaped quotes are unescaped.
Multiline strings and Python blocks are out of scope for Phase 1.
"""

import os
import re
from pathlib import Path

from app.core.extractor.models import ExtractedLine

__all__ = ["extract_renpy_file", "extract_renpy_folder"]

# speaker "dialogue"  |  "narration"  (no VERBOSE: '#' would start a comment)
_LINE_RE = re.compile(
    r"^\s*(?:(?P<speaker>[a-zA-Z_]\w*)\s+)?(?P<q>[\"'])(?P<text>(?:\\.|(?!(?P=q)).)*)(?P=q)\s*(?:\#.*)?$"
)

# lines that are clearly not dialogue: labels, jumps, python, $, etc.
_SKIP_RE = re.compile(
    r"^\s*(?:label|jump|call|return|menu|if|elif|else|while|for|python|init|define|image|scene|show|hide|with|play|stop|queue|voice|window|#|$|\"\"\"|''')"
)


def _clean(text: str) -> str:
    text = text.replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")
    # strip Ren'Py text tags like {fast}, {w=0.5}, {color=...}
    text = re.sub(r"\{[^}]*\}", "", text)
    return text.strip()


def extract_renpy_file(path: str) -> list[ExtractedLine]:
    """Extract dialogue lines from a single .rpy file."""
    out: list[ExtractedLine] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for no, raw in enumerate(fh, 1):
                if not raw.strip() or raw.lstrip().startswith("#"):
                    continue
                if _SKIP_RE.match(raw):
                    continue
                m = _LINE_RE.match(raw.rstrip("\n"))
                if not m:
                    continue
                text = _clean(m.group("text") or "")
                if not text:
                    continue
                speaker = (m.group("speaker") or "").strip()
                # skip ATL/transform property lines like "xpos 0.5"
                if speaker and " " in speaker:
                    continue
                out.append(
                    ExtractedLine(
                        speaker=speaker or "narrator",
                        text=text,
                        source_file=os.path.basename(path),
                        line_no=no,
                    )
                )
    except OSError:
        return []
    return out


def extract_renpy_folder(game_path: str) -> list[ExtractedLine]:
    """Extract dialogue from all .rpy files under game/ (or root)."""
    root = Path(game_path)
    candidates = sorted((root / "game").glob("*.rpy")) or sorted(root.rglob("*.rpy"))
    lines: list[ExtractedLine] = []
    for fp in candidates:
        if fp.is_file():
            lines.extend(extract_renpy_file(str(fp)))
    return lines
