"""Manifest-based install and uninstall without any game or TTS runtime."""

import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest

from app.core.replacer import install
from app.core.replacer.install import install_mod, uninstall_mod
from app.core.replacer.lock import game_lock, lock_info
from app.core.replacer.manifest import ModManifest


@pytest.fixture
def game_files(tmp_path):
    game = tmp_path / "game"
    output = tmp_path / "output"
    output.mkdir()
    pairs = []
    for index, name in enumerate(("voice/маяк.wav", "voice/arrival.wav", "other/arrival.wav")):
        target = game / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"original {index}".encode())
        source = output / f"{index}.wav"
        source.write_bytes(f"dub {index}".encode())
        pairs.append((name, str(source)))
    return game, pairs, output


@pytest.fixture
def mod(game_files):
    game, pairs, output = game_files
    path, manifest = install_mod(str(game), pairs, str(output))
    backup_dir = game.parent / ".agv-backups" / manifest.install_id
    return path, manifest, backup_dir


def assert_originals(game_files):
    game, pairs, _ = game_files
    for index, (relative, _) in enumerate(pairs):
        assert (game / relative).read_bytes() == f"original {index}".encode()


def test_install_creates_manifest_and_backups(game_files, mod):
    game, pairs, output = game_files
    path, manifest, backup_dir = mod
    assert Path(path) == game.parent / ".agv-manifests" / f"{manifest.install_id}.json"
    assert re.fullmatch(r"\d{8}T\d{6}\.\d{6}Z-[0-9a-f]{6}", manifest.install_id)
    assert manifest.created_at.endswith("+00:00")
    assert (manifest.game_root, manifest.output_dir) == (str(game), str(output))
    assert ModManifest.from_json(path) == manifest
    assert "маяк" in Path(path).read_text(encoding="utf-8")
    assert len(list(backup_dir.glob("*.bak"))) == 3
    if sys.platform != "win32":
        assert stat.S_IMODE(backup_dir.stat().st_mode) == 0o700
    for index, (entry, (relative, source)) in enumerate(zip(manifest.entries, pairs)):
        original = f"original {index}".encode()
        generated = Path(source).read_bytes()
        assert entry.original == relative and entry.replaced_with == f"{index}.wav"
        assert entry.status == "installed" and entry.uninstalled_at is None
        assert entry.installed_at.endswith("+00:00")
        assert (backup_dir / entry.backup).read_bytes() == original
        assert (game / relative).read_bytes() == generated
        assert entry.sha256_original == sha256(original).hexdigest()
        assert entry.sha256_replaced == sha256(generated).hexdigest()


def test_uninstall_restores_three_originals(game_files, mod):
    path, _, backup_dir = mod
    report = uninstall_mod(path)
    assert report == dict(restored=3, conflicts=[], missing=[], already_uninstalled=0, errors=[])
    assert_originals(game_files)
    assert not backup_dir.exists()
    entries = ModManifest.from_json(path).entries
    assert all(entry.status == "uninstalled" and entry.uninstalled_at.endswith("+00:00")
               for entry in entries)


def test_uninstall_is_idempotent(mod):
    path, _, _ = mod
    uninstall_mod(path)
    assert uninstall_mod(path) == dict(
        restored=0, conflicts=[], missing=[], already_uninstalled=3, errors=[],
    )


def test_uninstall_preserves_conflicting_file_and_backup(game_files, mod):
    path, manifest, backup_dir = mod
    game, _, _ = game_files
    entry = manifest.entries[0]
    changed = game / entry.original
    changed.write_bytes(b"player edit")
    report = uninstall_mod(path)
    assert report["restored"] == 2 and report["conflicts"] == [entry.original]
    assert changed.read_bytes() == b"player edit"
    assert (backup_dir / entry.backup).read_bytes() == b"original 0"
    assert ModManifest.from_json(path).entries[0].status == "conflict"
    assert uninstall_mod(path)["conflicts"] == [entry.original]


def test_uninstall_reports_missing_backup_without_changing_target(game_files, mod):
    path, manifest, backup_dir = mod
    game, _, _ = game_files
    entry = manifest.entries[0]
    (backup_dir / entry.backup).unlink()
    report = uninstall_mod(path)
    assert report["restored"] == 2 and report["missing"] == [entry.original]
    assert (game / entry.original).read_bytes() == b"dub 0"
    assert backup_dir.is_dir()
    assert ModManifest.from_json(path).entries[0].status == "missing"


def test_missing_original_is_rejected_before_replacing_any_file(game_files):
    game, pairs, output = game_files
    with pytest.raises(FileNotFoundError):
        install_mod(str(game), [*pairs, ("absent.wav", pairs[0][1])], str(output))
    assert_originals(game_files)
    assert not list((game.parent / ".agv-backups").glob("*"))
    assert not list((game.parent / ".agv-manifests").glob("*.json"))


def test_install_rejects_a_target_symlink_that_leaves_the_game(game_files):
    game, pairs, output = game_files
    outside = game.parent / "outside.wav"
    outside.write_bytes(b"outside")
    try:
        (game / "link.wav").symlink_to(outside)
    except (NotImplementedError, PermissionError):
        pytest.skip("Creating symlinks is unavailable")
    with pytest.raises(ValueError, match="Path outside"):
        install_mod(str(game), [*pairs, ("link.wav", pairs[0][1])], str(output))
    assert outside.read_bytes() == b"outside"
    assert_originals(game_files)


def test_failed_third_copy_rolls_back_installed_files(game_files, monkeypatch):
    game, pairs, output = game_files
    copy = shutil.copy2

    def fail_on_third(source, destination):
        if Path(source) == Path(pairs[2][1]):
            assert (game / pairs[0][0]).read_bytes() == b"dub 0"
            assert (game / pairs[1][0]).read_bytes() == b"dub 1"
            Path(destination).write_bytes(b"partial write")
            raise OSError("third copy failed")
        return copy(source, destination)

    monkeypatch.setattr(shutil, "copy2", fail_on_third)
    with pytest.raises(OSError, match="third copy failed"):
        install_mod(str(game), pairs, str(output))
    assert_originals(game_files)
    assert not list((game.parent / ".agv-backups").glob("*"))
    assert not list((game.parent / ".agv-manifests").glob("*.json"))


def test_failed_manifest_write_leaves_uninstall_safe_to_retry(game_files, mod, monkeypatch):
    game, pairs, _ = game_files
    path, manifest, backup_dir = mod

    def fail_to_save(*args):
        raise OSError("manifest write failed")

    with monkeypatch.context() as patch:
        patch.setattr(install, "_save_manifest", fail_to_save)
        result = uninstall_mod(path)
    assert result["restored"] == 0 and len(result["errors"]) == 3
    assert ModManifest.from_json(path) == manifest
    assert len(list(backup_dir.glob("*.bak"))) == 3
    assert [(game / relative).read_bytes() for relative, _ in pairs] == [
        b"dub 0", b"dub 1", b"dub 2",
    ]
    assert uninstall_mod(path)["restored"] == 3


def test_uninstall_rejects_a_corrupt_backup(game_files, mod):
    game, _, _ = game_files
    path, manifest, backup_dir = mod
    entry = manifest.entries[0]
    backup = backup_dir / entry.backup
    backup.write_bytes(b"corrupt")
    result = uninstall_mod(path)
    assert result["restored"] == 2
    assert result["errors"] == [{
        "original": entry.original, "error": "Backup SHA-256 does not match the manifest",
    }]
    assert backup.read_bytes() == b"corrupt"
    assert (game / entry.original).read_bytes() == b"dub 0"
    assert ModManifest.from_json(path).entries[0].status == "installed"


@pytest.mark.parametrize(("field", "bad_value"), [
    ("original", "../outside.wav"),
    ("backup", "/tmp/outside.bak"),
    ("sha256_replaced", "g" * 64),
    ("status", "unknown"),
])
def test_invalid_manifest_is_rejected(mod, field, bad_value):
    _, manifest, _ = mod
    manifest.entries[0] = replace(manifest.entries[0], **{field: bad_value})
    with pytest.raises(ValueError):
        manifest.validate()


def test_cli_install_and_uninstall_exit_codes(game_files):
    game, pairs, output = game_files
    cli = [sys.executable, "-B", "-m", "app.main"]
    args = ["install", "--game", str(game), "--output", str(output)]
    for target, source in pairs:
        args.extend(("--map", f"{target}:{Path(source).name}"))
    installed = subprocess.run([*cli, *args], capture_output=True, text=True, check=True)
    manifest_path = installed.stdout.strip()
    assert Path(manifest_path).is_file()
    (game / pairs[0][0]).write_bytes(b"manual edit")
    args = ["uninstall", "--manifest", manifest_path]
    conflict = subprocess.run([*cli, *args], capture_output=True, text=True)
    assert conflict.returncode == 1
    report = json.loads(conflict.stdout)
    assert report["conflicts"] == [pairs[0][0]] and report["restored"] == 2
    installed = subprocess.run([*cli, "install", "--game", str(game), "--output", str(output),
                                "--map", f"{pairs[0][0]}:{Path(pairs[0][1]).name}"],
                               capture_output=True, text=True, check=True)
    restored = subprocess.run([*cli, "uninstall", "--manifest", installed.stdout.strip()],
                              capture_output=True, text=True, check=True)
    assert json.loads(restored.stdout)["restored"] == 1
    assert (game / pairs[0][0]).read_bytes() == b"manual edit"


def test_stale_lock_from_crashed_process_is_taken_over(game_files, caplog):
    game, pairs, output = game_files
    child = subprocess.run(
        [sys.executable, "-B", "-c",
         "import os, sys; from pathlib import Path; from app.core.replacer.lock import game_lock\n"
         "with game_lock(Path(sys.argv[1])): os._exit(19)", str(game)],
        timeout=10, capture_output=True, text=True,
    )
    assert child.returncode == 19, child.stderr
    path = game.parent / ".agv-manifests" / f".{game.name}.lock"
    assert lock_info(path)["pid"] != os.getpid()
    manifest, _ = install_mod(str(game), pairs, str(output))
    assert Path(manifest).is_file()
    assert not path.exists()
    assert "Stale lock from dead process, taking over" in caplog.text


def test_active_lock_reports_the_owner_and_keeps_the_lock(game_files):
    game, _, _ = game_files
    with game_lock(game) as directory:
        path = directory / f".{game.name}.lock"
        before = lock_info(path)
        assert before["pid"] == os.getpid() and before["host"] == socket.gethostname()
        with pytest.raises(RuntimeError, match=f"install already running, pid={os.getpid()}"):
            with game_lock(game):
                pytest.fail("a second owner acquired the active lock")
        assert lock_info(path) == before
    assert not path.exists()


def test_invalid_and_foreign_locks_are_taken_over(game_files, caplog):
    game, _, _ = game_files
    directory = game.parent / ".agv-manifests"
    directory.mkdir()
    path = directory / f".{game.name}.lock"
    foreign = {
        "pid": os.getpid(), "started_at": "2026-11-23T09:00:00Z",
        "host": socket.gethostname() + "-remote",
    }
    for payload in ("{broken", json.dumps(foreign), None):
        caplog.clear()
        if payload is None:
            path.mkdir()  # Legacy directory lock.
        else:
            path.write_text(payload, encoding="utf-8")
        with game_lock(game):
            current = lock_info(path)
            assert current["pid"] == os.getpid()
            assert current["host"] == socket.gethostname()
            assert "Stale lock" in caplog.text and "taking over" in caplog.text
        assert not path.exists()


def test_release_preserves_a_lock_written_by_another_pid(game_files):
    game, _, _ = game_files
    with game_lock(game) as directory:
        path = directory / f".{game.name}.lock"
        foreign = {**lock_info(path), "pid": os.getpid() + 1}
        path.write_text(json.dumps(foreign), encoding="utf-8")
    assert lock_info(path) == foreign


def run_manifests(directory, *args):
    cli = Path(__file__).resolve().parents[1] / "app" / "main.py"
    return subprocess.run(
        [sys.executable, "-B", str(cli), "manifests", *args],
        cwd=directory, capture_output=True, text=True, check=True, timeout=10,
    ).stdout


def test_manifests_list_empty_directory(tmp_path):
    (tmp_path / ".agv-manifests").mkdir()
    assert run_manifests(tmp_path, "list") == ""


def test_manifests_list_status_counts_and_game_filter(game_files, mod):
    game, pairs, output = game_files
    complete_path, complete, _ = mod
    assert uninstall_mod(complete_path)["restored"] == 3
    other_game = game.with_name("other game")
    shutil.copytree(game, other_game)
    _, active = install_mod(str(other_game), pairs, str(output))
    rows = [line.split("\t") for line in run_manifests(game.parent, "list").splitlines()]
    assert rows[0] == [
        "install_id", "created_at", "game_root", "total", "installed", "uninstalled",
        "conflict", "missing", "age",
    ]
    assert len(rows) == 3
    counts = {row[0]: row[2:] for row in rows[1:]}
    assert counts[complete.install_id] == [str(game), "3", "0", "3", "0", "0", "0d"]
    assert counts[active.install_id] == [str(other_game), "3", "3", "0", "0", "0", "0d"]
    filtered = run_manifests(output, "list", "--game", str(other_game)).splitlines()
    assert len(filtered) == 2 and filtered[1].split("\t")[0] == active.install_id


def test_manifests_prune_dry_run_preserves_the_record(game_files, mod):
    game, _, _ = game_files
    path, _, _ = mod
    uninstall_mod(path)
    before = Path(path).read_bytes()
    assert run_manifests(game.parent, "prune", "--dry-run") == f"Would remove {path}\n"
    assert Path(path).read_bytes() == before


def test_manifests_prune_keeps_active_conflict_and_missing(game_files, mod):
    game, pairs, output = game_files
    completed, _, _ = mod
    uninstall_mod(completed)
    conflict, _ = install_mod(str(game), pairs, str(output))
    (game / pairs[0][0]).write_bytes(b"manual change")
    assert uninstall_mod(conflict)["conflicts"] == [pairs[0][0]]
    missing, missing_manifest = install_mod(str(game), pairs, str(output))
    missing_backup = game.parent / ".agv-backups" / missing_manifest.install_id
    (missing_backup / missing_manifest.entries[0].backup).unlink()
    assert uninstall_mod(missing)["missing"] == [pairs[0][0]]
    active, _ = install_mod(str(game), pairs, str(output))

    assert run_manifests(game.parent, "prune") == f"Removed {completed}\n"
    assert not Path(completed).exists()
    assert all(Path(path).is_file() for path in (active, conflict, missing))


def test_manifests_prune_filters_by_created_at(game_files, mod):
    game, pairs, output = game_files
    old_path, _, _ = mod
    uninstall_mod(old_path)
    old = ModManifest.from_json(old_path)
    old.created_at = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    Path(old_path).write_text(old.to_json(), encoding="utf-8")
    recent_path, _ = install_mod(str(game), pairs, str(output))
    uninstall_mod(recent_path)

    assert run_manifests(game.parent, "prune", "--older-than", "30d") == f"Removed {old_path}\n"
    assert not Path(old_path).exists() and Path(recent_path).is_file()
