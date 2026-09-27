"""Config tests (isolated via ANYGAMEVOICE_HOME)."""

import os


def test_save_show_delete(monkeypatch, tmp_path):
    monkeypatch.setenv("ANYGAMEVOICE_HOME", str(tmp_path))
    from app.utils.config import Config, delete_data, show_data

    assert show_data() == {}
    cfg = Config.load()
    cfg.set("engine", "piper")
    cfg.set_hardware({"ram_gb": 16}, {"tier": "recommended"})
    path = cfg.save()
    assert path.is_file()
    assert show_data()["engine"] == "piper"
    assert show_data()["hardware"]["ram_gb"] == 16
    assert delete_data() is True
    assert show_data() == {}
    assert delete_data() is False


def test_corrupt_config(monkeypatch, tmp_path):
    monkeypatch.setenv("ANYGAMEVOICE_HOME", str(tmp_path))
    from app.utils import config as cfgmod

    p = cfgmod.get_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not json{{{", encoding="utf-8")
    assert cfgmod.load_config() == {}
