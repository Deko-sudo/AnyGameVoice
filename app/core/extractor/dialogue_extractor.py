"""Dialogue extractor.

Routes to the engine-specific extractor based on detect_engine().
Phase 1: Ren'Py is implemented; other engines return [].
"""

import os

from app.core.extractor.models import ExtractedLine

__all__ = ["extract_dialogue"]


def extract_dialogue(game_path: str) -> list:
    """Extract dialogue lines (list of ExtractedLine). Empty if unsupported."""
    if not game_path or not os.path.isdir(game_path):
        return []
    try:
        from app.core.game_detector.detector import detect_engine
    except Exception:
        detect_engine = lambda _p: "unknown"  # noqa: E731

    engine = detect_engine(game_path)
    if engine == "renpy":
        from app.core.game_detector.engines.renpy import extract_renpy_folder

        return extract_renpy_folder(game_path)
    return []
