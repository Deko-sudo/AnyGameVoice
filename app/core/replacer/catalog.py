"""CLI commands for inspecting and pruning a directory of mod manifests."""

import argparse
import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .lock import game_lock
from .manifest import ModManifest

logger = logging.getLogger(__name__)


def _read_record(path: Path) -> tuple[ModManifest, datetime] | None:
    try:
        if not path.is_file() or path.is_symlink():
            return None
        manifest = ModManifest.from_json(path)
        stamp = manifest.created_at
        if not isinstance(stamp, str):
            raise ValueError("created_at requires an ISO 8601 timestamp")
        created_at = datetime.fromisoformat(stamp[:-1] + "+00:00" if stamp.endswith("Z") else stamp)
        if created_at.utcoffset() is None:
            raise ValueError("created_at requires a timezone")
        return manifest, created_at
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning("Skipping unreadable manifest %s: %s", path, exc)
        return None


def _older_than(value: str) -> timedelta:
    if not re.fullmatch(r"[0-9]+d", value):
        raise argparse.ArgumentTypeError("use a number of days such as 30d")
    try:
        return timedelta(days=int(value[:-1]))
    except (OverflowError, ValueError) as exc:
        raise argparse.ArgumentTypeError("number of days is too large") from exc


def _prunable(
    path: Path, manifest: ModManifest, age: timedelta, older_than: timedelta | None,
) -> bool:
    game = Path(manifest.game_root).resolve()
    return (
        path.name == f"{manifest.install_id}.json"
        and path.parent == game.parent / ".agv-manifests"
        and (older_than is None or age >= older_than)
        and bool(manifest.entries)
        and all(entry.status == "uninstalled" for entry in manifest.entries)
    )


def manifests_command(argv: list[str], prog: str) -> None:
    parser = argparse.ArgumentParser(prog=prog)
    sub = parser.add_subparsers(dest="action", required=True)
    list_parser, prune_parser = sub.add_parser("list"), sub.add_parser("prune")
    for command in (list_parser, prune_parser):
        command.add_argument("--game", type=Path, help="show or prune records for this game only")
    prune_parser.add_argument("--older-than", type=_older_than, metavar="DAYS")
    prune_parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    game = args.game.resolve() if args.game is not None else None
    directory = (game.parent if game is not None else Path.cwd()) / ".agv-manifests"
    if directory.is_symlink():
        raise ValueError(f"Mod storage cannot be a symlink: {directory}")

    now = datetime.now(timezone.utc)
    rows = []
    statuses = ("installed", "uninstalled", "conflict", "missing")
    for path in sorted(directory.glob("*.json"), reverse=True):
        record = _read_record(path)
        if record is None:
            continue
        manifest, created_at = record
        manifest_game = Path(manifest.game_root).resolve()
        if game is not None and manifest_game != game:
            continue
        age = now - created_at
        if args.action == "list":
            counts = Counter(entry.status for entry in manifest.entries)
            rows.append((manifest.install_id, manifest.created_at, manifest.game_root, len(manifest.entries),
                         *(counts[status] for status in statuses), f"{max(0, age.days)}d"))
        elif _prunable(path, manifest, age, args.older_than):
            if args.dry_run:
                print(f"Would remove {path}")
                continue
            with game_lock(manifest_game):
                current = _read_record(path)
                if current is not None:
                    current_manifest, current_created_at = current
                    if (Path(current_manifest.game_root).resolve() == manifest_game
                            and _prunable(path, current_manifest, now - current_created_at, args.older_than)):
                        path.unlink()
                        print(f"Removed {path}")
    if rows:
        print("\t".join(("install_id", "created_at", "game_root", "total", *statuses, "age")))
        for row in rows:
            print("\t".join(map(str, row)))
