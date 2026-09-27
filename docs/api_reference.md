# API Reference

## CLI (`python app/main.py ...`)

| Command | Description |
|---------|-------------|
| `scan <folder>` | Hardware + access + folder/engine/audio report (JSON) |
| `extract <folder>` | Print first 20 dialogue lines |
| `mod <folder> --out <dir> [--voice m.onnx] [--engine piper] [--workers 2]` | Batch TTS + `dialogue.srt` |
| `ui [port]` | Local web UI (`http://127.0.0.1:8000`) |
| `config [--show\|--delete\|--save-scan]` | Privacy controls |
| `unpack <target> --out <dir> [--engine auto\|unity\|unreal] [--unrealpak path] [--aes-key key]` | Carve/unpack containers |
| `translate "text" --to ru [--from en] [--provider ollama]` | One-line translation |

## Core

- `app.core.scanner.hardware.scan_hardware() -> dict`, `recommend_settings(hw) -> dict`
- `app.core.scanner.permissions.request_permission(name)`, `check_path_access(path)`
- `app.core.game_detector.detector.detect_engine(path) -> str`, `scan_game_folder(path) -> dict`
- `app.core.extractor.dialogue_extractor.extract_dialogue(path) -> list[ExtractedLine]`, `supported_engines()`
- `app.core.tts.generator.generate_voice(text, voice, engine) -> bytes`,
  `generate_voice_to_file(...)`, `list_engines()`, `get_engine(name, voice)`
- `app.core.tts.voice_manager.VoiceManager(user_dir).list_voices()/add_voice()/remove_voice()`
- `app.core.replacer.audio_replacer.replace_audio(target, source, make_backup=True) -> backup_path`
- `app.core.replacer.backup.backup_file(path)`, `restore_file(backup, original="")`
- `app.core.queue.task_queue.TaskQueue(workers).submit(func, ..., priority, name)`, `.wait()`, `.wait_all()`, `.shutdown()`

## Models (`app.models`)

`Dialogue`, `Character`, `Voice`, `Project` (dataclasses), `ExtractedLine` (`app.core.extractor.models`).

## Providers / Agent

- `app.providers.router.get_provider(name, api_key="", model="")`, `list_providers()`
- `AIAgent(provider="ollama", search="tavily").research(topic, max_pages=3)`

## Utils

- `app.utils.config.Config`, `load/save/show/delete` (local `~/.anygamevoice/config.json`)
- `app.utils.audio_utils.estimate_duration/to_srt/to_vtt/fmt_timestamp`
- `app.utils.audio_utils.find_embedded_audio/carve_embedded_audio`
- `app.core.tts.emotions.parse_emotion/strip_emotion_tags/piper_flags/apply_emotion`
- `app.core.translate.translate_text/translate_lines`
- `app.ui_server.start_mod_job/mod_job_status` (+ `POST /api/mod`, `GET /api/mod/{id}`)
- `app.utils.file_utils.ensure_dir`, `app.utils.logger.log`
