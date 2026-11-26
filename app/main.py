"""
AnyGameVoice - AI Voice Modding Tool
Main entry point
"""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

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


def cmd_mod(folder: str, out: str, voice: str = "", engine: str = "piper", workers: int = 2, emotion: str = "neutral",
            translate_to: str = "", provider: str = "ollama") -> dict:
    """Generate audio and return the same per-line report exposed by the UI."""
    from app.core.extractor.dialogue_extractor import extract_dialogue
    from app.core.queue.task_queue import TaskQueue, TaskStatus
    from app.core.translate import translate_line
    from app.core.tts.generator import generate_voice_to_file
    from app.utils.audio_utils import to_srt

    lines = extract_dialogue(folder)
    output = Path(out)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with TemporaryDirectory(dir=output, prefix=".agv-batch-") as batch:
        ready = Path(batch) / "ready"
        ready.mkdir()

        def synthesize(line, index):
            # A worker may outlive the batch. Keep its open file private until
            # synthesis completes, including on Windows where it cannot be unlinked.
            with TemporaryDirectory(dir=output, prefix=".agv-tts-") as scratch:
                wav = Path(scratch) / "line.wav"
                generate_voice_to_file(line, str(wav), engine=engine)
                wav.replace(ready / f"{index}.wav")

        q = TaskQueue(workers=workers)
        jobs = []
        try:
            for i, line in enumerate(lines):
                result = {
                    "index": i, "source_file": line.source_file, "line_no": line.line_no,
                    "speaker": line.speaker, "status": "failed", "skipped_reason": None,
                }
                results.append(result)
                if translate_to:
                    try:
                        line = translate_line(line, translate_to, provider=provider)
                    except Exception as exc:
                        result["skipped_reason"] = f"Translation failed: {str(exc) or type(exc).__name__}"
                        continue
                line.voice_id = line.voice_id or voice
                if line.emotion == "neutral":
                    line.emotion = emotion
                name = f"{i:04d}_{line.speaker or 'narrator'}.wav"
                tid = q.submit(synthesize, line, i, name=name)
                jobs.append((tid, line, result))
        finally:
            q.shutdown(wait=True, timeout=60)

        # Seal the directory atomically. A late writer can no longer add files
        # while the report is finalized or the temporary directory is removed.
        finished = ready.rename(Path(batch) / "finished")
        completed = []
        for tid, line, result in jobs:
            task = q.status(tid)
            if task["status"] == TaskStatus.DONE:
                try:
                    (finished / f"{result['index']}.wav").replace(output / task["name"])
                except OSError as exc:
                    result["skipped_reason"] = f"Could not publish WAV: {exc}"
                else:
                    result.update(status="succeeded", wav=task["name"])
                    completed.append(line)
            elif task["status"] == TaskStatus.FAILED:
                result["skipped_reason"] = task["error"].splitlines()[0] or "TTS failed"
            elif task["status"] == TaskStatus.TIMEOUT:
                result["skipped_reason"] = "TTS timed out"

    total, succeeded = len(lines), len(completed)
    failed = total - succeeded
    if not succeeded:
        status = "failed"
    elif failed:
        status = "partial"
    else:
        status = "done"
    error = f"{failed} of {total} lines failed" if failed else ""
    if not total:
        error = "No dialogue extracted"
    report = {
        "status": status, "total": total, "succeeded": succeeded, "failed": failed,
        "error": error, "lines": results,
    }
    (output / "dialogue.srt").write_text(to_srt(completed), encoding="utf-8")
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {succeeded}/{total} lines -> {out} ({status})")
    for result in results:
        if result["skipped_reason"]:
            print(f"SKIPPED {result['source_file']}:{result['line_no']}: {result['skipped_reason']}")
    return report


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


def cmd_translate(text: str, to: str, source: str = "auto", provider: str = "ollama"):
    """Translate one line via the provider router."""
    import os as _os

    from app.core.translate import translate_text

    print(translate_text(text, target=to, source=source, provider=provider,
                         api_key=_os.environ.get("TRANSLATE_API_KEY", "")))


def cmd_ui(port: int = 8000):
    """Launch the local web UI."""
    from app.ui_server import run

    print(f"AnyGameVoice UI: http://127.0.0.1:{port}  (Ctrl+C to stop)")
    run(port=port)


def _prog() -> str:
    """CLI invocation prefix (dev vs frozen bundle)."""
    if getattr(sys, "frozen", False):
        import os as _os

        return _os.path.basename(sys.executable)
    return "python app/main.py"


def main(argv=None):
    """Main entry point for the application."""
    argv = sys.argv[1:] if argv is None else argv
    prog = _prog()
    if not argv:
        # Packaged CLI callers also pipe the banner to identify the executable.
        if getattr(sys, "frozen", False) and sys.stdout and not sys.stdout.isatty():
            argv = ["--help"]
        else:
            return cmd_ui()
    if argv in (["--help"], ["-h"], ["help"]):
        _banner()
        print()
        print("  Status: Ready — CLI + local web UI")
        print("  License: Apache 2.0")
        print()
        print("  Usage:")
        print(f"    {prog} scan <game_folder>")
        print(f"    {prog} extract <game_folder>")
        print(f"    {prog} mod <game_folder> --out <dir> [--voice model.onnx] [--engine piper] [--emotion neutral] [--translate-to ru] [--workers 2]")
        print(f"    {prog} install --game PATH --output PATH --map ORIG:GEN [--map ...]")
        print(f"    {prog} uninstall --manifest PATH")
        print(f"    {prog} manifests list [--game PATH]")
        print(f"    {prog} manifests prune [--game PATH] [--older-than 30d] [--dry-run]")
        print(f"    {prog} unpack <game_or_container> --out <dir> [--engine auto|unity|unreal]")
        print(f"    {prog} translate \"text\" --to ru [--provider ollama]")
        print(f"    {prog} ui [port]")
        print(f"    {prog} config [--show|--delete|--save-scan]")
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
        p.add_argument("--emotion", default="neutral")
        p.add_argument("--translate-to", default="")
        p.add_argument("--provider", default="ollama")
        p.add_argument("--workers", type=int, default=2)
        a = p.parse_args(rest)
        report = cmd_mod(a.folder, a.out, voice=a.voice, engine=a.engine, workers=a.workers,
                         emotion=a.emotion, translate_to=a.translate_to, provider=a.provider)
        if report["status"] != "done":
            raise SystemExit(1)
    elif cmd in ("install", "uninstall"):
        import argparse

        from app.core.replacer.install import install_mod, uninstall_mod

        parser = argparse.ArgumentParser(prog=f"{prog} {cmd}")
        if cmd == "install":
            parser.add_argument("--game", required=True)
            parser.add_argument("--output", required=True)
            parser.add_argument("--map", action="append", required=True, metavar="ORIG:GEN")
            args = parser.parse_args(rest)
            output = Path(args.output).resolve()
            replacements = []
            for mapping in args.map:
                original, _, generated = mapping.partition(":")
                if not original or not generated:
                    parser.error("--map requires an original and a generated path (ORIG:GEN)")
                replacements.append((original, str(output / generated)))
            try:
                path, _ = install_mod(args.game, replacements, str(output))
            except (OSError, ValueError, RuntimeError) as exc:
                print(f"install: {exc}", file=sys.stderr)
                raise SystemExit(1) from exc
            print(path)
        else:
            parser.add_argument("--manifest", required=True)
            args = parser.parse_args(rest)
            try:
                report = uninstall_mod(args.manifest)
            except (OSError, ValueError, RuntimeError) as exc:
                print(f"uninstall: {exc}", file=sys.stderr)
                raise SystemExit(1) from exc
            print(json.dumps(report, ensure_ascii=False, indent=2))
            if report["conflicts"] or report["missing"] or report["errors"]:
                raise SystemExit(1)
    elif cmd == "manifests":
        from app.core.replacer.catalog import manifests_command

        try:
            manifests_command(rest, f"{prog} manifests")
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"manifests: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
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
    elif cmd == "translate" and rest:
        import argparse

        p = argparse.ArgumentParser(prog="translate")
        p.add_argument("text")
        p.add_argument("--to", required=True)
        p.add_argument("--from", dest="source", default="auto")
        p.add_argument("--provider", default="ollama")
        a = p.parse_args(rest)
        cmd_translate(a.text, a.to, source=a.source, provider=a.provider)
    else:
        print(f"Unknown command: {cmd}. Try: scan | extract | ui | config | mod | install | uninstall | manifests | unpack | translate")
        sys.exit(2)


if __name__ == "__main__":
    main()
