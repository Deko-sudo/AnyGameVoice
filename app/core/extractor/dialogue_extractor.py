"""Dialogue extractor.

Routes to the engine-specific extractor based on detect_engine().
Implemented: Ren'Py (.rpy), RPG Maker (Map JSON), Godot (.dialogue).
Unity/Unreal: compiled assets, text extraction not supported yet
(use scan audio inventory + replacer instead).
"""

import os

from app.core.extractor.models import ExtractedLine

__all__ = ["extract_dialogue", "supported_engines"]

SUPPORTED = ("renpy", "rpgmaker", "godot")


def supported_engines() -> tuple:
    """Engines with text extraction."""
    return SUPPORTED


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
    if engine == "rpgmaker":
        from app.core.game_detector.engines.rpgmaker import extract_rpgmaker_folder

        return extract_rpgmaker_folder(game_path)
    if engine == "godot":
        from app.core.game_detector.engines.godot import extract_godot_folder

        return extract_godot_folder(game_path)
    return []
