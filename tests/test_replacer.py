"""Replacer tests."""

import os


def test_backup_and_restore(tmp_path):
    from app.core.replacer.backup import backup_file, restore_file

    f = tmp_path / "sfx.wav"
    f.write_bytes(b"original")
    bak = backup_file(str(f))
    assert bak.endswith(".bak")
    assert os.path.isfile(bak)
    f.write_bytes(b"modified")
    restored = restore_file(bak)
    assert open(restored, "rb").read() == b"original"


def test_replace_audio(tmp_path):
    from app.core.replacer.audio_replacer import replace_audio

    target = tmp_path / "voice.wav"
    target.write_bytes(b"game-audio")
    src = tmp_path / "gen.wav"
    src.write_bytes(b"ai-audio")
    bak = replace_audio(str(target), str(src))
    assert bak.endswith(".bak")
    assert open(str(target), "rb").read() == b"ai-audio"
    # restore works
    from app.core.replacer.backup import restore_file

    restore_file(bak)
    assert open(str(target), "rb").read() == b"game-audio"
