# User Guide

## Workflow

1. **Scan** — `python app/main.py scan <folder>` (or the web UI).
   Check `engine`, `script_files`, `audio_files`. If the engine is
   `unknown`, text extraction is skipped but you can still use the
   replacer on known audio paths.
2. **Privacy** — the first hardware scan is opt-in. Stored data lives in
   `~/.anygamevoice/config.json`:
   `python app/main.py config --show` to view, `--delete` to wipe,
   `--save-scan` to refresh.
3. **Voices** — drop `.onnx`/`.wav` presets into `voices/presets/`,
   your samples into `voices/user/` (or `VoiceManager.add_voice()`).
   List via web UI or `VoiceManager().list_voices()`.
4. **Batch** — `python app/main.py mod <folder> --out ./out --voice <model>`:
   parallel TTS through the task queue, one wav per line, plus
   `dialogue.srt` for timing review.
5. **Replace** — `replace_audio(game_file, generated_wav)` always writes
   a `<name>.<timestamp>.bak` first; `restore_file(backup)` rolls back.
6. **Providers (optional)** — copy `.env.example` to `.env`, add keys for
   OpenAI/Anthropic/Groq/Mistral/DeepSeek/Tavily/Brave. Ollama needs no key
   (`OLLAMA_URL`, default `http://localhost:11434`). Keys never leave your
   machine except to the provider's own API.
7. **Agent (optional)** — `AIAgent(provider="ollama").research("piper russian voices")`
   searches the web, fetches pages and summarizes with citations.

## Engine notes

- **Ren'Py**: `speaker "text"` + narration; `{tags}` stripped; comments skipped.
- **RPG Maker MV/MZ**: event codes 101 (speaker) / 401 (text) / 102 (choices).
- **Godot**: Dialogue Manager `*.dialogue` (`Name: text`); `- choices` skipped.
- **Unity**: `unpack` carves WAV/Ogg/FSB5 from `.assets`/`.bundle`/`.resource`
  (or full AudioClip decode with optional UnityPy); text needs unpacked assets.
- **Unreal**: `unpack` sniffs `.pak` footers, uses UnrealPak CLI when present,
  carves `.ubulk` audio; encrypted paks need the game's AES key.

## Emotions & translation

- Prefix lines with `[happy]`, `[sad]`, `[angry]`, `[whisper]`, `[shouting]`
  (or `<emotion="sad">`). Piper maps them to prosody flags; bark keeps its
  native `[laughs]`/`[sighs]` markers; other engines get clean text.
  CLI: `mod ... --emotion happy`.
- `translate "Hello" --to ru --provider ollama`, or whole-pipeline
  `mod ... --translate-to ru --provider ollama` (emotion tags preserved).

## Desktop shell

`docs/tauri.md`: `cargo tauri dev` wraps the web UI in a native window,
spawning the Python backend automatically.

## Safety

- Game files are only written by `replace_audio`, always with backup.
- `voices/user/*` and `.env` are git-ignored; never commit keys or samples.
