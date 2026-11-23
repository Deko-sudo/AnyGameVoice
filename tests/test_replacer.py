"""Replacer tests."""

import logging
import os
import shutil
from pathlib import Path

import pytest

from app.core.replacer.audio_replacer import replace_audio, uninstall_audio
from app.core.replacer.backup import backup_file, restore_file


def test_backup_and_restore(tmp_path):
    f = tmp_path / "sfx.wav"
    f.write_bytes(b"original")
    bak = backup_file(str(f))
    assert bak.endswith(".bak")
    assert os.path.isfile(bak)
    f.write_bytes(b"modified")
    restored = restore_file(bak)
    assert Path(restored) == f and f.read_bytes() == b"original"
    assert not Path(bak).exists()
    with pytest.raises(FileNotFoundError, match="Backup not found"):
        restore_file(bak)


def test_restore_copy_error_keeps_backup(tmp_path, monkeypatch, caplog):
    target = tmp_path / "voice.wav"
    target.write_bytes(b"original")
    backup = Path(backup_file(str(target)))
    target.write_bytes(b"mod")

    def copy_error(src, dst):
        raise OSError("copy failed")

    monkeypatch.setattr(shutil, "copy2", copy_error)
    with pytest.raises(OSError, match="copy failed"):
        restore_file(str(backup))
    assert uninstall_audio(str(target), str(backup)) is False
    assert "copy failed" in caplog.text
    assert backup.read_bytes() == b"original"


def test_restore_refuses_same_file(tmp_path):
    backup = tmp_path / "voice.wav.bak"
    backup.write_bytes(b"only copy")
    alias = tmp_path / "voice.wav"
    alias.hardlink_to(backup)
    for target in (backup, alias):
        with pytest.raises(shutil.SameFileError):
            restore_file(str(backup), original=str(target))
        assert backup.read_bytes() == b"only copy"


def test_restore_accepts_already_removed_backup(tmp_path, monkeypatch):
    target = tmp_path / "voice.wav"
    target.write_bytes(b"original")
    backup = backup_file(str(target))
    target.write_bytes(b"mod")
    unlink = os.unlink

    def concurrent_unlink(path):
        unlink(path)
        raise FileNotFoundError(path)

    monkeypatch.setattr(os, "unlink", concurrent_unlink)
    assert restore_file(backup) == str(target)
    assert target.read_bytes() == b"original" and not Path(backup).exists()


def test_restore_and_uninstall_succeed_when_backup_cleanup_is_denied(tmp_path, monkeypatch, caplog):
    target = tmp_path / "voice.wav"
    target.write_bytes(b"original")
    backup = backup_file(str(target))

    def deny_unlink(path):
        raise PermissionError("cleanup denied")

    monkeypatch.setattr(os, "unlink", deny_unlink)
    target.write_bytes(b"mod")
    assert restore_file(backup) == str(target)
    assert target.read_bytes() == Path(backup).read_bytes() == b"original"
    assert any(record.levelno == logging.WARNING and backup in record.getMessage()
               and "cleanup denied" in record.getMessage() for record in caplog.records)

    target.write_bytes(b"mod")
    assert uninstall_audio(str(target), backup) is True
    assert target.read_bytes() == Path(backup).read_bytes() == b"original"


def test_replace_and_uninstall_audio(tmp_path):
    target = tmp_path / "voice.wav"
    target.write_bytes(b"game-audio")
    src = tmp_path / "gen.wav"
    src.write_bytes(b"ai-audio")
    bak = replace_audio(str(target), str(src))
    assert bak.endswith(".bak")
    assert target.read_bytes() == b"ai-audio"
    assert uninstall_audio(str(target), bak) is True
    assert target.read_bytes() == b"game-audio"
    assert not Path(bak).exists()


def test_uninstall_missing_backup(tmp_path, caplog):
    target = tmp_path / "voice.wav"
    target.write_bytes(b"mod")
    backup = str(target) + ".bak"
    assert uninstall_audio(str(target), backup) is False
    assert target.read_bytes() == b"mod"
    assert "Backup not found" in caplog.text and backup in caplog.text


def test_uninstall_rejects_another_targets_backup(tmp_path, caplog):
    first = tmp_path / "first.wav"
    first.write_bytes(b"original")
    backup = backup_file(str(first))
    first.write_bytes(b"mod")
    second = tmp_path / "second.wav"
    second.write_bytes(b"other")
    assert uninstall_audio(str(second), backup) is False
    assert "different target" in caplog.text
    assert second.read_bytes() == b"other" and first.read_bytes() == b"mod"
    assert Path(backup).read_bytes() == b"original"
