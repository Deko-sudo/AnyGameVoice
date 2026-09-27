"""Scanner tests."""


def test_scan_stub():
    from app.core.scanner.hardware import scan_hardware

    info = scan_hardware()
    assert isinstance(info, dict)
    assert "cpu_count" in info
    assert "ram_gb" in info
    assert "os" in info


def test_recommend_settings():
    from app.core.scanner.hardware import recommend_settings

    s = recommend_settings({"ram_gb": 32, "vram_gb": 12})
    assert s["tier"] == "ideal"
    s = recommend_settings({"ram_gb": 8, "vram_gb": 0})
    assert s["tier"] == "minimum"


def test_path_access(tmp_path):
    from app.core.scanner.permissions import check_path_access

    ok = check_path_access(str(tmp_path))
    assert ok["exists"] and ok["readable"]
    missing = check_path_access(str(tmp_path / "nope"))
    assert not missing["exists"]
