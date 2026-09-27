"""Replacer tests."""


def test_backup_stub():
    from app.core.replacer.backup import backup_file

    assert backup_file("a.wav").endswith(".bak")
