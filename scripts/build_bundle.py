"""Build a native single-file bundle with PyInstaller.

What gets bundled:
  - entry app/main.py (all CLI commands + `ui` server)
  - data: ui/ (SPA), voices/presets/
  - runtime deps: fastapi/uvicorn/requests/bs4/psutil/GPUtil

Deliberately EXCLUDED (optional backends, clean runtime errors instead):
  torch/TTS/bark/scipy/numpy/soundfile/UnityPy — install them with pip
  to use xtts/bark/silero/UnityPy paths with `python app/main.py`,
  the bundle stays lean (~30-60MB).

Usage:
  pip install pyinstaller
  python scripts/build_bundle.py [--mode onefile|onedir] [--name anygamevoice]
  python scripts/build_bundle.py --tauri-sidecar [--target TRIPLE]

--tauri-sidecar copies dist/<name> to
src-tauri/binaries/<name>-<target-triple>[.exe] for `cargo tauri build`.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Optional heavy backends: never bundle, code degrades to clear errors.
EXCLUDES = [
    "torch", "torchaudio", "TTS", "transformers", "bark", "scipy",
    "numpy", "soundfile", "UnityPy", "librosa", "numba", "llvmlite",
    "tensorflow", "sklearn", "matplotlib", "PIL",
]

# Lazy imports PyInstaller must not miss (all inside functions).
HIDDEN = [
    "app.ui_server",
    "app.main",
    "app.core.tts.generator",
    "app.core.tts.emotions",
    "app.core.translate",
    "app.providers.router",
    "app.agent.ai_agent",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
]


def detect_triple() -> str:
    """Rust target triple for the current host."""
    machine = platform.machine().lower()
    arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
    if sys.platform == "win32":
        return f"{arch}-pc-windows-msvc"
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    return f"{arch}-unknown-linux-gnu"


def build(name: str = "anygamevoice", mode: str = "onefile") -> str:
    """Run PyInstaller. Returns the produced binary path."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("PyInstaller not installed. Run: pip install pyinstaller") from exc
    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onedir" if mode == "onedir" else "--onefile",
        "--console",
        "--name", name,
        f"--add-data=ui{sep}ui",
        f"--add-data=voices{sep}voices",
        "--paths", REPO,
    ]
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    for mod in HIDDEN:
        cmd += ["--hidden-import", mod]
    cmd.append(os.path.join(REPO, "app", "main.py"))
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, cwd=REPO, check=True)
    ext = ".exe" if sys.platform == "win32" else ""
    binary = os.path.join(REPO, "dist", name + ext)
    if not os.path.isfile(binary):
        raise RuntimeError(f"Build finished but {binary} is missing")
    size_mb = os.path.getsize(binary) / (1024 * 1024)
    print(f"Built: {binary} ({size_mb:.1f} MB)")
    return binary


def tauri_sidecar(binary: str, name: str, triple: str = "") -> str:
    """Copy bundle to src-tauri/binaries/<name>-<triple>[.exe]."""
    triple = triple or detect_triple()
    ext = ".exe" if triple.endswith("windows-msvc") else ""
    dest_dir = os.path.join(REPO, "src-tauri", "binaries")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{name}-{triple}{ext}")
    shutil.copy2(binary, dest)
    print(f"Sidecar: {dest}")
    print("Declare it in tauri.conf.json > bundle.externalBin, then `cargo tauri build`.")
    return dest


def main(argv=None) -> int:
    """CLI entry."""
    parser = argparse.ArgumentParser(description="Build AnyGameVoice native bundle.")
    parser.add_argument("--name", default="anygamevoice")
    parser.add_argument("--mode", default="onefile", choices=["onefile", "onedir"])
    parser.add_argument("--tauri-sidecar", action="store_true")
    parser.add_argument("--target", default="", help="Rust triple for sidecar name")
    parser.add_argument("--skip-build", action="store_true", help="only (re)stage existing dist binary as sidecar")
    args = parser.parse_args(argv)
    if args.skip_build:
        ext = ".exe" if sys.platform == "win32" else ""
        binary = os.path.join(REPO, "dist", args.name + ext)
        if not os.path.isfile(binary):
            raise RuntimeError(f"No dist binary at {binary}; build first.")
    else:
        binary = build(args.name, args.mode)
    if args.tauri_sidecar:
        tauri_sidecar(binary, args.name, args.target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
