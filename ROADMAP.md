# Roadmap

## Completed

- [x] Project initialization
- [x] Repository setup
- [x] Phase 1 — Core engine (scan, Ren'Py extract, Piper, replacer)
- [x] Phase 2 — Local web UI (FastAPI + offline SPA)
- [x] Phase 3 — Hardware auto-detect + local config/privacy controls
- [x] Phase 4 — Voice freedom (piper/xtts/bark/silero registry)
- [x] Phase 5 — AI providers (openai/anthropic/groq/mistral/deepseek/ollama)
- [x] Phase 6 — Built-in AI agent + web search
- [x] Phase 7 — Priority task queue
- [x] Phase 8 — RPG Maker / Godot extractors, Unity/Unreal inventory
- [x] Phase 9 — Subtitles (SRT/VTT) + batch `mod` pipeline
- [x] Phase 10 — Docs + distribution scripts
- [x] Unity unpacking (carve WAV/Ogg/FSB5, optional UnityPy decode)
- [x] Unreal unpacking (pak inspect, UnrealPak CLI, .ubulk carve)
- [x] Emotions (`[tag]` -> piper prosody / bark markers)
- [x] Translation (provider router, `translate` CLI, `mod --translate-to`)
- [x] Tauri desktop shell scaffold + `/api/mod` background jobs

## Next

- [ ] Native single-file bundle (PyInstaller sidecar for Tauri)
- [ ] Unity AssetBundle / Unreal .pak *text* extraction (needs unpackers)
- [ ] Lip-sync timing export
- [ ] Auto-updater + signed releases
