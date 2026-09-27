"""Bundle/path tests (offline, no PyInstaller run)."""

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_resource_paths_dev():
    from app.utils.paths import preset_dir, project_root, resource_path, user_voices_dir

    assert resource_path("ui", "index.html").is_file()
    assert preset_dir() == project_root() / "voices" / "presets"
    assert preset_dir().is_dir()
    os.environ.pop("ANYGAMEVOICE_HOME", None)
    assert ".anygamevoice" in str(user_voices_dir())


def test_voice_manager_dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("ANYGAMEVOICE_HOME", str(tmp_path))
    from app.core.tts.voice_manager import PRESET_DIR, USER_DIR

    assert PRESET_DIR.is_dir()  # shipped dir inside the repo, not a stray home path
    assert USER_DIR == tmp_path / "voices"


def test_build_script_help():
    proc = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "build_bundle.py"), "--help"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert proc.returncode == 0
    assert "--tauri-sidecar" in proc.stdout


def test_triple_detect():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "build_bundle", os.path.join(REPO, "scripts", "build_bundle.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    triple = mod.detect_triple()
    assert triple.startswith(("x86_64-", "aarch64-"))
    assert triple.endswith(("windows-msvc", "unknown-linux-gnu", "apple-darwin"))
