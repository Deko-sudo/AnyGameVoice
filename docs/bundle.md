# Native Bundle (PyInstaller)

Single-file executable with the full CLI + web UI, no Python needed
on the target machine (~13-16MB, console app).

## Build locally

```bash
pip install pyinstaller
python scripts/build_bundle.py            # -> dist/anygamevoice[.exe]
python scripts/build_bundle.py --mode onedir   # faster starts, a folder
```

What's inside: `app/*` code, `ui/` SPA, `voices/presets/`, and the
runtime closure (fastapi/uvicorn/requests/bs4/psutil).
Optional heavy backends (torch/TTS/bark/scipy/numpy/soundfile/UnityPy)
are **excluded on purpose** — that code prints a clear install hint
instead of bloating the bundle. Use `python app/main.py` with pip
packages for xtts/bark/silero/UnityPy paths.

## Use

```bash
dist/anygamevoice scan <game_folder>
dist/anygamevoice ui 8000
```

First run unpacks to a temp dir (few seconds), then behaves exactly
like `python app/main.py`. Config/voices live in `~/.anygamevoice`
(`ANYGAMEVOICE_HOME` override), never inside the bundle.

If a stale `dist/anygamevoice.exe` blocks rebuild on Windows, a copy
is still running — stop it first (the script reports WinError 5).

## Tauri sidecar

```bash
python scripts/build_bundle.py --tauri-sidecar [--target TRIPLE]
```

Copies the binary to
`src-tauri/binaries/anygamevoice-<triple>[.exe]` (git-ignored,
declared in `tauri.conf.json > bundle.externalBin`). The Rust shell
(`src-tauri/src/main.rs`) prefers the sidecar and falls back to
`python app/main.py ui` in dev. Then `cargo tauri build`.

## CI / releases

`.github/workflows/build.yml`: builds Windows + Linux + macOS on
manual dispatch, attaches bundles to GitHub Releases on `v*` tags:

```bash
git tag v0.1.0 && git push origin v0.1.0
```
