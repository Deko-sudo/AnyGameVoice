"""
AnyGameVoice - AI Voice Modding Tool
Main entry point
"""

import json
import sys
from pathlib import Path

# Allow `python app/main.py` (script dir is app/, project root must be on path)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _banner():
    print("=" * 50)
    print("  AnyGameVoice v0.1.0")
    print("  AI Voice Modding Tool")
    print("=" * 50)


def cmd_scan(folder: str):
    """Scan hardware + game folder."""
    from app.core.game_detector.detector import scan_game_folder
    from app.core.scanner.hardware import recommend_settings, scan_hardware
    from app.core.scanner.permissions import check_path_access

    hw = scan_hardware()
    print(json.dumps({"hardware": hw, "recommend": recommend_settings(hw)}, indent=2, ensure_ascii=False))
    access = check_path_access(folder)
    print(json.dumps({"access": access}, indent=2, ensure_ascii=False))
    if access["exists"]:
        print(json.dumps(scan_game_folder(folder), indent=2, ensure_ascii=False))


def cmd_extract(folder: str, limit: int = 20):
    """Extract dialogue and print first lines."""
    from app.core.extractor.dialogue_extractor import extract_dialogue

    lines = extract_dialogue(folder)
    print(f"Extracted {len(lines)} lines from {folder}")
    for ln in lines[:limit]:
        print(f"[{ln.source_file}:{ln.line_no}] {ln.speaker}: {ln.text}")


def cmd_config(action: str):
    """Privacy controls: --show / --delete, or save current hardware scan."""
    from app.utils.config import delete_data, show_data

    if action == "--show":
        print(json.dumps(show_data(), indent=2, ensure_ascii=False))
    elif action == "--delete":
        print("deleted" if delete_data() else "nothing stored")
    elif action == "--save-scan":
        from app.core.scanner.hardware import recommend_settings, scan_hardware
        from app.utils.config import Config

        hw = scan_hardware()
        cfg = Config.load()
        cfg.set_hardware(hw, recommend_settings(hw))
        print(f"saved to {cfg.save()}")
    else:
        print("Usage: python app/main.py config [--show|--delete|--save-scan]")
        sys.exit(2)


def cmd_ui(port: int = 8000):
    """Launch the local web UI."""
    from app.ui_server import run

    print(f"AnyGameVoice UI: http://127.0.0.1:{port}  (Ctrl+C to stop)")
    run(port=port)


def main(argv=None):
    """Main entry point for the application."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        _banner()
        print()
        print("  Status: Phase 1 - Core Engine")
        print("  License: Apache 2.0")
        print()
        print("  Usage:")
        print("    python app/main.py scan <game_folder>")
        print("    python app/main.py extract <game_folder>")
        print("    python app/main.py ui [port]")
        print("    python app/main.py config [--show|--delete|--save-scan]")
        print()
        print("=" * 50)
        return
    cmd, *rest = argv
    if cmd == "scan" and rest:
        cmd_scan(rest[0])
    elif cmd == "extract" and rest:
        cmd_extract(rest[0])
    elif cmd == "ui":
        cmd_ui(int(rest[0]) if rest else 8000)
    elif cmd == "config" and rest:
        cmd_config(rest[0])
    else:
        print(f"Unknown command: {cmd}. Try: scan | extract | ui | config")
        sys.exit(2)


if __name__ == "__main__":
    main()
