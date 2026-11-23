"""Prepare a Ren'Py audio mod and verify restoration for a manual smoke test."""

import argparse
import hashlib
import json
import logging
import re
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.core.game_detector.engines.renpy import extract_renpy_file
from app.core.replacer.manifest import ModManifest

LOG_NAME = "phase1_5.log"
STATE_NAME = "phase1_5_state.json"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
VOICE = re.compile(r"""^([ \t]*)voice[ \t]+(["'])(.+?)\2[ \t]*(?:#.*)?$""")
logger = logging.getLogger("phase1_5")


def run_cli(step, *args):
    logger.info("%s · agv %s", step, shlex.join(args))
    result = subprocess.run(
        [sys.executable, "-B", str(REPO / "app/main.py"), *args],
        capture_output=True, text=True,
    )
    if result.stdout.strip():
        logger.info("%s", result.stdout.rstrip())
    if result.stderr.strip():
        logger.warning("%s", result.stderr.rstrip())
    logger.info("Exit code %s", result.returncode)
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(path, state):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as audio:
        for block in iter(lambda: audio.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def voice_snapshot(game):
    root = game / "game/voice"
    if root.resolve() != root:
        raise ValueError(f"Voice directory points somewhere else: {root}")
    return {path.relative_to(root).as_posix(): sha256(path)
            for path in sorted(root.rglob("*")) if path.is_file() and not path.is_symlink()}


def voice_bindings(scripts, game):
    """Match literal voice directives to the next parsed line at the same indent."""
    root = game / "game"
    bindings, references = {}, Counter()
    for script in scripts:
        dialogue = {line.line_no: line for line in extract_renpy_file(str(script))}
        pending = None
        for number, raw in enumerate(script.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            stripped = raw.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            directive = VOICE.fullmatch(raw)
            if directive:
                indent, _, asset = directive.groups()
                relative = PurePosixPath(asset)
                pending = None
                if not relative.parts or relative.parts[0] != "voice" or ".." in relative.parts:
                    continue
                if any(char in asset for char in "\\:[]{}"):
                    continue
                path = root / relative
                if path.suffix.lower() != ".wav" or path.resolve() != path or not path.is_file():
                    continue
                references[path] += 1
                pending = (indent, path)
                continue
            if pending and number in dialogue and raw[:len(raw) - len(stripped)] == pending[0]:
                line = dialogue[number]
                bindings[(line.source_file, line.line_no, line.speaker)] = pending[1]
            pending = None
    return bindings, references


def build_mappings(report, scripts, game, output):
    bindings, references = voice_bindings(scripts, game)
    mappings = []
    for row in report["lines"]:
        location = (row["source_file"], row["line_no"], row["speaker"])
        if row["status"] != "succeeded":
            logger.warning("%s:%s · %s", *location[:2], row.get("skipped_reason") or "generation failed")
            continue
        original = bindings.get(location)
        if original is None:
            logger.info("%s:%s · no direct existing voice WAV", *location[:2])
            continue
        if references[original] > 1:
            logger.warning("%s:%s · shared voice WAV skipped: %s", *location[:2], original)
            continue
        generated = (output / row["wav"]).resolve()
        if generated.suffix.lower() != ".wav" or not generated.is_relative_to(output) or not generated.is_file():
            raise ValueError(f"Generated WAV is missing or outside output: {generated}")
        mapping = f"{original.relative_to(game).as_posix()}:{generated.relative_to(output).as_posix()}"
        mappings.extend(("--map", mapping))
        logger.info("%s:%s · %s", *location[:2], mapping)
    return mappings


def prepare(args, game, output):
    logger.info("1. Checking Ren'Py project %s", game)
    root = game / "game"
    scripts = [path for path in sorted(root.glob("*.rpy")) if path.is_file() and path.resolve() == path]
    if not scripts or not ((game / "renpy").is_dir() or (root / "script.rpy").is_file()):
        raise ValueError("Expected game/*.rpy and either a renpy/ directory or game/script.rpy")
    if not (root / "voice").is_dir():
        raise ValueError("Expected a game/voice/ directory")
    before = voice_snapshot(game)
    logger.info("Found %s scripts and %s files in game/voice/", len(scripts), len(before))

    if run_cli("2. Scan game", "scan", str(game)).returncode:
        logger.warning("Scan failed. Continuing with the validated game directory.")
    flags = ["--voice", str(args.voice.resolve())] if args.voice else []
    result = run_cli(
        "3. Generate dialogue", "mod", str(game), "--out", str(output),
        "--translate-to", args.target, "--engine", args.engine, "--provider", args.provider, *flags,
    )
    logger.info("4. Read report.json")
    report = read_json(output / "report.json")
    status = report["status"]
    logger.info("status=%s total=%s succeeded=%s failed=%s",
                status, report["total"], report["succeeded"], report["failed"])
    if (status, result.returncode) not in (("done", 0), ("partial", 1)):
        raise ValueError(f"Generation did not complete: {report.get('error') or status}")

    logger.info("5. Map report rows to literal Ren'Py voice paths")
    mappings = build_mappings(report, scripts, game, output)
    if not mappings:
        raise ValueError("No unambiguous existing WAVs to replace. See the mapping log.")
    if voice_snapshot(game) != before:
        raise ValueError("game/voice/ changed during generation. Start again on a clean copy.")
    state_path = output / STATE_NAME
    state = {"game_root": str(game), "manifest_path": None, "voice_sha256_before": before}
    write_state(state_path, state)
    result = run_cli("6. Install mapped WAVs", "install", "--game", str(game), "--output", str(output), *mappings)
    if result.returncode:
        raise ValueError("Install failed. See the CLI output above.")
    manifest = Path(result.stdout.strip()).resolve(strict=True)
    logger.info("7. Save manifest path to %s", state_path)
    state["manifest_path"] = str(manifest)
    write_state(state_path, state)
    command = shlex.join(["bash", str(REPO / "scripts/phase1_5_smoke.sh"), "--uninstall", str(manifest)])
    logger.info("8. Запусти игру в Ren'Py SDK, пройди обе ветки, закрой игру и выполни:\n%s", command)


def verify_originals(manifest, updated):
    game = Path(manifest.game_root)
    restored = {entry.original for entry in updated.entries if entry.status == "uninstalled"}
    problems = []
    for entry in manifest.entries:
        if entry.original not in restored:
            problems.append(f"{entry.original}: not restored")
            continue
        original = (game / entry.original).resolve()
        if (not original.is_relative_to(game) or not original.is_file()
                or sha256(original) != entry.sha256_original.lower()):
            problems.append(f"{entry.original}: original SHA-256 mismatch or file unavailable")
    return problems


def uninstall(path, manifest):
    result = run_cli("1. Uninstall the mod", "uninstall", "--manifest", str(path))
    logger.info("2. Check the uninstall report")
    report = json.loads(result.stdout)
    problems = []
    for key in ("conflicts", "missing", "errors"):
        problems.extend(f"{key}: {item}" for item in report[key])
        logger.info("%s=%s", key, len(report[key]))
    if result.returncode or report["restored"] + report["already_uninstalled"] != len(manifest.entries):
        problems.append(f"Uninstall exit {result.returncode}: restored={report['restored']}, "
                        f"already_uninstalled={report['already_uninstalled']}, total={len(manifest.entries)}")

    logger.info("3. Compare restored files with their manifest SHA-256 values")
    problems.extend(verify_originals(manifest, ModManifest.from_json(path)))
    state_path = Path(manifest.output_dir) / STATE_NAME
    state = read_json(state_path) if state_path.is_file() else {}
    if state.get("manifest_path") == str(path) and state.get("game_root") == manifest.game_root:
        logger.info("Compare the complete game/voice/ inventory with the baseline")
        before = state["voice_sha256_before"]
        after = voice_snapshot(Path(manifest.game_root))
        for name in sorted(before.keys() | after.keys()):
            if before.get(name) != after.get(name):
                problems.append(f"game/voice/{name}: added, removed or changed")
    else:
        logger.warning("No matching baseline state. Compared only files in the manifest.")
    logger.info("4. Verify result")
    for problem in problems:
        logger.error("%s", problem)
    if problems:
        return 1
    logger.info("OK")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--target")
    parser.add_argument("--engine", default="piper")
    parser.add_argument("--voice", type=Path, help="Piper .onnx model")
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--uninstall", type=Path, metavar="MANIFEST")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    handler = None
    try:
        if args.uninstall:
            if args.game or args.output or args.target or args.voice:
                parser.error("--uninstall takes a manifest instead of install options")
            path = args.uninstall.resolve(strict=True)
            manifest = ModManifest.from_json(path)
            output = Path(manifest.output_dir)
            if not output.is_dir():
                output = path.parent
        else:
            if not (args.game and args.output and args.target):
                parser.error("install requires --game, --output and --target")
            if args.engine == "piper" and not (args.voice and args.voice.is_file()):
                parser.error("Piper requires --voice pointing to an existing .onnx model")
            game, output = args.game.resolve(strict=True), args.output.resolve()
            if not game.is_dir() or output.is_relative_to(game):
                raise ValueError("Choose a game directory and an output directory outside it")
            output.mkdir(parents=True, exist_ok=True)
            if any(output.iterdir()):
                raise ValueError(f"Use an empty output directory for each run: {output}")
        handler = logging.FileHandler(output / LOG_NAME, encoding="utf-8")
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        if args.uninstall:
            return uninstall(path, manifest)
        prepare(args, game, output)
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        logger.error("%s", exc)
        return 1
    finally:
        if handler:
            logger.removeHandler(handler)
            handler.close()


if __name__ == "__main__":
    sys.exit(main())
