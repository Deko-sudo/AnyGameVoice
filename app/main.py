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


def cmd_mod(folder: str, out: str, voice: str = "", engine: str = "piper", workers: int = 2):
    """Batch pipeline: extract -> synthesize via queue -> wavs + SRT sidecar."""
    import os

    from app.core.extractor.dialogue_extractor import extract_dialogue
    from app.core.queue.priority import Priority
    from app.core.queue.task_queue import TaskQueue
    from app.core.tts.generator import generate_voice_to_file
    from app.utils.audio_utils import to_srt

    lines = extract_dialogue(folder)
    if not lines:
        print(f"No dialogue extracted from {folder}.")
        return
    os.makedirs(out, exist_ok=True)
    q = TaskQueue(workers=workers)
    jobs = []
    for i, ln in enumerate(lines):
        fname = f"{i:04d}_{(ln.speaker or 'narrator')}.wav"
        dest = os.path.join(out, fname)
        tid = q.submit(
            generate_voice_to_file, ln.text, dest, voice=voice, engine=engine,
            priority=Priority.NORMAL, name=fname,
        )
        jobs.append((tid, dest, ln))
    snaps = q.wait_all(timeout=600)
    q.shutdown()
    ok = sum(1 for s in snaps if s["status"] == "done")
    print(f"Generated {ok}/{len(snaps)} lines -> {out}")
    for s in snaps:
        if s["status"] == "failed":
            print(f"FAILED {s['name']}: {(s['error'] or '').splitlines()[0]}")
    srt_path = os.path.join(out, "dialogue.srt")
    with open(srt_path, "w", encoding="utf-8") as fh:
        fh.write(to_srt(lines))
    print(f"Subtitles: {srt_path}")


def cmd_unpack(target: str, out: str, engine: str = "auto", unrealpak: str = "", aes_key: str = ""):
    """Unpack Unity/Unreal containers (carve + optional native tools)."""
    import json as _json
    import os as _os

    from app.core.game_detector.detector import detect_engine

    eng = engine
    if eng == "auto":
        base = target if _os.path.isdir(target) else _os.path.dirname(target) or "."
        eng = detect_engine(base)
        if _os.path.isfile(target):
            low = target.lower()
            if low.endswith((".assets", ".bundle", ".resource")):
                eng = "unity"
            elif low.endswith((".pak", ".utoc", ".ucas", ".ubulk")):
                eng = "unreal"
    if eng == "unity":
        from app.core.game_detector.engines.unity import extract_unity_audio

        res = extract_unity_audio(target if _os.path.isdir(target) else _os.path.dirname(target), out)
    elif eng == "unreal":
        from app.core.game_detector.engines.unreal import extract_unreal_audio, inspect_pak

        base = target if _os.path.isdir(target) else target
        if _os.path.isfile(target) and target.lower().endswith(".pak"):
            print(_json.dumps(inspect_pak(target), indent=2))
        res = extract_unreal_audio(base if _os.path.isdir(base) else _os.path.dirname(base), out,
                                   unrealpak=unrealpak, aes_key=aes_key)
    else:
        print(f"unpack: unsupported engine '{eng}' (need unity/unreal game or container).")
        sys.exit(2)
    print(_json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in res.items()}, indent=2))
    for kind in ("unitypy", "unpacked", "carved"):
        for p in res.get(kind, [])[:20]:
            print(f"  [{kind}] {p}")


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
        print("    python app/main.py mod <game_folder> --out <dir> [--voice model.onnx] [--engine piper] [--workers 2]")
        print("    python app/main.py unpack <game_or_container> --out <dir> [--engine auto|unity|unreal] [--unrealpak path] [--aes-key key]")
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
    elif cmd == "mod" and rest:
        import argparse

        p = argparse.ArgumentParser(prog="mod")
        p.add_argument("folder")
        p.add_argument("--out", required=True)
        p.add_argument("--voice", default="")
        p.add_argument("--engine", default="piper")
        p.add_argument("--workers", type=int, default=2)
        a = p.parse_args(rest)
        cmd_mod(a.folder, a.out, voice=a.voice, engine=a.engine, workers=a.workers)
    elif cmd == "unpack" and rest:
        import argparse

        p = argparse.ArgumentParser(prog="unpack")
        p.add_argument("target")
        p.add_argument("--out", required=True)
        p.add_argument("--engine", default="auto")
        p.add_argument("--unrealpak", default="")
        p.add_argument("--aes-key", default="")
        a = p.parse_args(rest)
        cmd_unpack(a.target, a.out, engine=a.engine, unrealpak=a.unrealpak, aes_key=a.aes_key)
    else:
        print(f"Unknown command: {cmd}. Try: scan | extract | ui | config | mod | unpack")
        sys.exit(2)


if __name__ == "__main__":
    main()
