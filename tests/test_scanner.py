"""Scanner tests."""


def test_scan_stub():
    from app.core.scanner.hardware import scan_hardware

    assert isinstance(scan_hardware(), dict)
