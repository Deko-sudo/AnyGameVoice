"""Game engine detector.

Heuristic detection based on well-known marker files.
No game content is read beyond file names.
"""

import os
from pathlib import Path

__all__ = ["detect_engine", "scan_game_folder"]

ENGINE_MARKERS = {
    "renpy": ("game/*.rpy", "game/*.rpyc", "renpy/", "game/options.rpy"),
    "rpgmaker": ("Game.rpgproject", "www/js/rpg_core.js", "js/rpg_core.js", "data/System.json"),
    "unity": ("*_Data/", "*.assets", "Managed/Assembly-CSharp.dll"),
    "unreal": ("*.uproject", "*.pak"),
    "godot": ("project.godot", "*.pck"),
}


def _has_pattern(root: Path, pattern: str) -> bool:
    try:
        return any(root.glob(pattern))
    except Exception:
        return False


def detect_engine(game_path: str) -> str:
    """Detect game engine from folder markers. Returns engine id or "unknown"."""
    if not game_path or not os.path.isdir(game_path):
        return "unknown"
    root = Path(game_path)
    scores = {}
    for engine, patterns in ENGINE_MARKERS.items():
        scores[engine] = sum(1 for p in patterns if _has_pattern(root, p))
        # also search one level deep for nested layouts
        if scores[engine] == 0:
            try:
                for child in root.iterdir():
                    if child.is_dir() and any(child.glob(p) for p in patterns):
                        scores[engine] += 1
                        break
            except OSError:
                pass
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "unknown"


def scan_game_folder(game_path: str, max_files: int = 5000) -> dict:
    """List folder stats: file count, total size, interesting subpaths."""
    result: dict = {
        "path": game_path,
        "exists": False,
        "engine": "unknown",
        "files": 0,
        "size_mb": 0.0,
        "script_files": [],
    }
    if not game_path or not os.path.isdir(game_path):
        return result
    result["exists"] = True
    result["engine"] = detect_engine(game_path)
    total = 0
    count = 0
    scripts: list = []
    for dirpath, _dirs, files in os.walk(game_path):
        for name in files:
            count += 1
            fp = os.path.join(dirpath, name)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
            if name.endswith((".rpy", ".rpyc", ".json", ".js", ".uproject", ".godot")):
                rel = os.path.relpath(fp, game_path)
                if len(scripts) < 50:
                    scripts.append(rel)
            if count >= max_files:
                break
        if count >= max_files:
            break
    result["files"] = count
    result["size_mb"] = round(total / (1024 * 1024), 1)
    result["script_files"] = scripts
    return result
