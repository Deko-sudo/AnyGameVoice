# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Phase 1 core engine:
  - Hardware scan + recommended settings (`app/core/scanner`)
  - Game folder scan + engine detection for Ren'Py/RPG Maker/Unity/Unreal/Godot
  - Ren'Py .rpy dialogue extractor
  - Piper TTS adapter + voice manager (local presets/user voices)
  - Audio replacer with timestamped backup + restore
  - CLI: `python app/main.py scan|extract <game_folder>`
  - Tests for scanner, detector, extractor, TTS, replacer
- Phase 2: local web UI (`ui/index.html` offline SPA, `app/ui_server.py` FastAPI, `main.py ui`)
- Phase 3: local JSON config + privacy controls (`config --show/--delete/--save-scan`)
- Phase 4: TTS registry (piper/xtts/bark/silero, `list_engines`)
- Phase 5: AI providers over HTTP (openai/anthropic/groq/mistral/deepseek/ollama + router)
- Phase 6: AI agent (`AIAgent.research`), Tavily/Brave search, page parse, webview
- Phase 7: threaded priority `TaskQueue` with result/error capture
- Phase 8: RPG Maker Map JSON + Godot `.dialogue` extractors, Unity/Unreal audio inventory,
  detector tie bug fix
- Phase 9: SRT/VTT subtitles + batch `mod` pipeline (queue TTS -> wavs + sidecar)
- Phase 10: full docs (guide/install/user/plugin/api/faq), real `download_models.py`,
  CLI usage in README
- Unity unpacking: magic-byte carver (WAV/Ogg/FSB5), UnityPy AudioClip decode
  with carve fallback, `unpack` CLI
- Unreal unpacking: `.pak` footer sniff, UnrealPak locate/run, `.ubulk` carve
- Emotions: `[tag]`/`<emotion>` parsing, piper prosody flags, bark marker
  passthrough, `mod --emotion`
- Translation via provider router (`translate` CLI, `mod --translate-to`)
- Tauri shell scaffold (`src-tauri/`, backend spawn/kill, `docs/tauri.md`),
  `/api/mod` background jobs + web UI panel

### Fixed
- `.gitignore` `models/` shadowed `app/models/` (narrowed to `/models/`)
- `python app/main.py` missing project root on `sys.path`
- Detector tie bug: bare `child.glob()` generators are always truthy
  (any subfolder gave +1 to every engine)
- `ui_server.INDEX` pointed at `app/index.html` instead of `ui/index.html`

### Fixed
- `.gitignore` `models/` shadowed `app/models/` (narrowed to `/models/`)
- `python app/main.py` missing project root on `sys.path`
- README with project description
- Apache 2.0 license
- Privacy policy
- Disclaimer
- Contributing guidelines
- Issue templates
- Basic Python project configuration
