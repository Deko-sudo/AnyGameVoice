# Tauri Desktop Shell

Native window around the existing Python backend + web UI.
No logic is reimplemented in Rust: the shell spawns
`python app/main.py ui 8000` on startup and kills it on exit.

## Layout

- `tauri.conf.json` — `frontendDist: ../ui` (the static SPA),
  `devUrl: http://127.0.0.1:8000`, `beforeDevCommand` starts the backend.
- `src/main.rs` — spawn backend if port 8000 is free, kill on `RunEvent::Exit`.
- `capabilities/default.json` — minimal (`core:default` + dragging).
- Icons: generate via `cargo tauri icon path/to/logo.png` into
  `src-tauri/icons/` (referenced by the config, not yet committed).

## Dev

```bash
cargo install tauri-cli --version "^2"
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
cargo tauri dev
```

## Build

```bash
cargo tauri build
```

Output: `src-tauri/target/release/bundle/`. The bundle currently
expects a system Python with the repo's requirements installed
(companion-backend model). Single-file distribution via a PyInstaller
sidecar is the documented next step, not yet implemented.

## Notes

- `cargo check` needs crates.io access; some locked-down machines
  (AppLocker/WDAC) block locally built build-scripts — use a normal
  dev machine or GitHub-hosted CI runners.
- The web UI also runs standalone (`python app/main.py ui 8000`),
  so the desktop shell is strictly optional.
