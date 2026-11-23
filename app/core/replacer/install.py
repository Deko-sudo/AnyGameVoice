"""Install and uninstall a group of audio replacements recorded in a manifest."""

import hashlib
import logging
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from .backup import _remove_backup, backup_file, restore_file
from .lock import game_lock
from .manifest import ManifestEntry, ModManifest, _atomic_write, _relative_path, _utc_now

__all__ = ["install_mod", "uninstall_mod"]

logger = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside(root: Path, relative: str) -> Path:
    path = (root / _relative_path(relative)).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError(f"Path outside {root}: {relative}")
    return path


def _storage(path: Path) -> Path:
    if path.is_symlink():
        raise ValueError(f"Mod storage cannot be a symlink: {path}")
    return path


def _save_manifest(manifest: ModManifest, path: Path) -> None:
    _atomic_write(path, manifest.to_json())


def _replacement_paths(
    game: Path, output: Path, replacements: list[tuple[str, str]],
) -> list[tuple[Path, Path]]:
    if not replacements:
        raise ValueError("At least one replacement is required")
    pairs = []
    originals = set()
    for original, generated in replacements:
        target = _inside(game, Path(original).as_posix())
        source = Path(generated)
        if not source.is_absolute():
            raise ValueError(f"Generated path must be absolute: {source}")
        source = source.resolve()
        if not source.is_relative_to(output):
            raise ValueError(f"Generated file is outside output_dir: {source}")
        for path in (target, source):
            if not path.is_file():
                raise FileNotFoundError(f"Audio file not found: {path}")
        if target in originals:
            raise ValueError(f"Duplicate target: {target}")
        originals.add(target)
        pairs.append((target, source))
    if any(source in originals for _, source in pairs):
        raise ValueError("A generated file is also a target in this install")
    return pairs


def _rollback(applied: list[tuple[Path, Path]]) -> list[str]:
    errors = []
    for target, backup in reversed(applied):
        try:
            with TemporaryDirectory(dir=target.parent) as staging:
                staged = Path(staging) / target.name
                restore_file(str(backup), str(staged), remove_backup=False)
                staged.replace(target)
        except OSError as exc:
            errors.append(f"{target}: {exc}")
    return errors


def install_mod(
    game_root: str, replacements: list[tuple[str, str]], output_dir: str,
) -> tuple[str, ModManifest]:
    """Replace mapped files and publish a manifest after every replacement succeeds."""
    game, output = Path(game_root).resolve(), Path(output_dir).resolve()
    if not game.is_dir():
        raise ValueError(f"Invalid game directory: {game}")
    if not output.is_dir():
        raise NotADirectoryError(output)
    with game_lock(game) as manifests:
        pairs = _replacement_paths(game, output, replacements)
        now = datetime.now(timezone.utc)
        install_id = f"{now:%Y%m%dT%H%M%S.%fZ}-{secrets.token_hex(3)}"
        manifest = ModManifest(install_id, now.isoformat(), str(game), str(output), [])
        path = manifests / f"{install_id}.json"
        if path.exists() or path.is_symlink():
            raise FileExistsError(path)
        backups = _storage(game.parent / ".agv-backups")
        backups.mkdir(mode=0o700, exist_ok=True)
        backup_dir = backups / install_id
        backup_dir.mkdir(mode=0o700)
        applied = []
        try:
            for index, (target, source) in enumerate(pairs):
                backup = backup_dir / f"{index:04d}.bak"
                backup_file(str(target), destination=backup)
                original_hash = _sha256(backup)
                with TemporaryDirectory(dir=target.parent) as staging:
                    staged = Path(staging) / target.name
                    shutil.copy2(source, staged)
                    replacement_hash = _sha256(staged)
                    if _sha256(target) != original_hash:
                        raise RuntimeError(f"Target changed during install: {target}")
                    staged.replace(target)
                    applied.append((target, backup))
                manifest.entries.append(ManifestEntry(
                    target.relative_to(game).as_posix(), backup.name,
                    source.relative_to(output).as_posix(), original_hash,
                    replacement_hash, _utc_now(),
                ))
            _save_manifest(manifest, path)
        except BaseException as exc:
            failures = _rollback(applied)
            if failures:
                details = "; ".join(failures)
                raise RuntimeError(f"Rollback incomplete. Backups at {backup_dir}. {details}") from exc
            shutil.rmtree(backup_dir)
            raise
    return str(path), manifest


def _restore_entry(
    manifest: ModManifest, entry: ManifestEntry, path: Path, target: Path, backup: Path,
) -> bool:
    """Publish the original and its status before consuming the backup."""
    with TemporaryDirectory(dir=target.parent, ignore_cleanup_errors=True) as staging:
        previous = Path(staging) / "previous"
        staged = Path(staging) / "original"
        shutil.copy2(target, previous)
        restore_file(str(backup), str(staged), remove_backup=False)
        if _sha256(staged) != entry.sha256_original.lower():
            raise ValueError("Backup SHA-256 does not match the manifest")
        if _sha256(previous) != entry.sha256_replaced.lower() or _sha256(target) != entry.sha256_replaced.lower():
            return False
        staged.replace(target)
        entry.status = "uninstalled"
        entry.uninstalled_at = _utc_now()
        try:
            _save_manifest(manifest, path)
        except BaseException:
            entry.status = "installed"
            entry.uninstalled_at = None
            previous.replace(target)
            raise
    _remove_backup(backup, target)
    return True


def uninstall_mod(manifest_path: str) -> dict:
    """Restore matching files, retain unresolved backups, and report per-file outcomes."""
    path = Path(manifest_path).resolve()
    game = Path(ModManifest.from_json(path).game_root).resolve()
    report = dict(restored=0, conflicts=[], missing=[], already_uninstalled=0, errors=[])
    with game_lock(game):
        manifest = ModManifest.from_json(path)
        if Path(manifest.game_root).resolve() != game:
            raise ValueError("Manifest game directory changed")
        backups = _storage(game.parent / ".agv-backups")
        backup_dir = _storage(backups / manifest.install_id)
        for entry in manifest.entries:
            if entry.status == "uninstalled":
                report["already_uninstalled"] += 1
                continue
            if entry.status == "conflict":
                report["conflicts"].append(entry.original)
                continue
            if entry.status == "missing":
                report["missing"].append(entry.original)
                continue
            try:
                target = _inside(game, entry.original)
                backup = _inside(backup_dir, entry.backup)
                if not backup.is_file() or not target.exists():
                    status, category = "missing", "missing"
                elif _sha256(target) != entry.sha256_replaced.lower():
                    status, category = "conflict", "conflicts"
                elif _restore_entry(manifest, entry, path, target, backup):
                    report["restored"] += 1
                    continue
                else:
                    status, category = "conflict", "conflicts"
                entry.status = status
                try:
                    _save_manifest(manifest, path)
                except OSError:
                    entry.status = "installed"
                    raise
                report[category].append(entry.original)
            except (OSError, ValueError) as exc:
                report["errors"].append({"original": entry.original, "error": str(exc)})
        if all(entry.status == "uninstalled" for entry in manifest.entries):
            if backup_dir.is_dir() and not any(backup_dir.iterdir()):
                try:
                    backup_dir.rmdir()
                except OSError as exc:
                    logger.warning("Could not remove empty backup directory %s: %s", backup_dir, exc)
    return report
