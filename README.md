# 🎮 AnyGameVoice

**Free, open-source AI voice modding tool.**

Drop a game folder → Choose voices → Get AI-generated voice-overs.

No ads. No tracking. No paywalls. Just modding.

---

## ✨ Features

- 🎯 **Drag & Drop** — Just drop your game folder
- 🤖 **AI-Powered** — Uses TTS models to generate voice lines
- 🎭 **Voice Freedom** — Choose any voice, clone your own, or use presets
- 🔌 **Plugin System** — Support for multiple game engines
- 🔒 **Privacy First** — Everything runs locally, no data collection
- ⚡ **Smart Detection** — Auto-detects your hardware and recommends settings
- 🌐 **Multi-Provider** — Connect your own AI provider (OpenAI, Claude, Groq, Ollama)

## 🎯 Supported Engines

| Engine | Status | Notes |
|--------|--------|-------|
| Ren'Py | ✅ Planned | First priority |
| RPG Maker | 🔜 Coming | MV/MZ support |
| Unity | 🔜 Coming | AssetBundle parsing |
| Unreal Engine | 🔜 Coming | .pak file support |
| Godot | 📋 Backlog | Future support |

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- (Optional) NVIDIA GPU with CUDA for faster generation

### Installation

```bash
git clone https://github.com/Deko-sudo/AnyGameVoice.git
cd AnyGameVoice
pip install -r requirements.txt
python app/main.py
```

No Python on the target machine? Grab (or build) the single-file bundle —
see [docs/bundle.md](docs/bundle.md):

```bash
python scripts/build_bundle.py   # -> dist/anygamevoice[.exe]
dist/anygamevoice ui 8000
```

### Usage

```bash
python app/main.py scan <game_folder>     # hardware + engine report
python app/main.py extract <game_folder>  # dialogue lines
python app/main.py mod <game_folder> --out ./out --voice models/en_US-lessac-medium.onnx
python app/main.py ui 8000                # local web UI
```

1. Launch the application (CLI or web UI)
2. Scan your game folder (engine auto-detected)
3. Choose voices for characters
4. Batch-generate wavs + subtitles
5. Install into the game with automatic backups

### Uninstalling a mod

Keep the backup path returned by `replace_audio` for each file you install.
Pass that path and the same target to `uninstall_audio` when removing the mod.

```python
from app.core.replacer.audio_replacer import replace_audio, uninstall_audio

target = "game/voice/beacon.wav"
backup = replace_audio(target, "output/0000_e.wav")
# Later, restore the original clip.
restored = uninstall_audio(target, backup)
```

`True` means the original was restored. The backup is normally removed.
If cleanup fails, the call still returns `True` and logs a warning with the
backup path and reason. If restoration fails, the call returns `False` and
logs the error. A failed copy leaves the backup available for a retry.
Calling `restore_file(backup)` after the backup has been removed raises
`FileNotFoundError`.

Uninstall currently operates on one file per call. Manifest-based uninstall
for an entire mod is planned for Phase 1.

### Job status

The web UI shows the result of each batch with its succeeded/total and failed/total counts.

| Status | Meaning |
|--------|---------|
| `done` | Every extracted line produced a WAV. |
| `partial` | At least one line produced a WAV and at least one failed. Successful WAVs and their subtitles are available. |
| `failed` | No line succeeded, no dialogue was found, or the job ended with a batch-level error. |

### Batch report

Each completed batch writes `report.json` in the output directory chosen with
`--out` or the web UI, alongside the WAVs and `dialogue.srt`. The UI reads the
same result from `GET /api/mod/{job_id}`.

| Field | Contents |
|-------|----------|
| `status`, `error` | Final job status and a summary of any failures. |
| `total`, `succeeded`, `failed` | Extracted lines, WAVs produced, and lines that failed. |
| `lines` | One entry per extracted line, in source order, with a zero-based `index`, `source_file`, `line_no`, `speaker`, and per-line `status`. |
| `lines[].wav` | Output filename for a `succeeded` line. |
| `lines[].skipped_reason` | Failure reason for a `failed` line, or `null` on success. |

Once all lines have been submitted, workers share a 60-second deadline to
finish the queue. Any unfinished line counts as failed with the reason
`TTS timed out`. Only successful lines appear in the subtitles.

### Translation and voice limitations

- Bark keeps sound markers such as `[laughs]` and `[sighs]`. Piper, XTTS and
  Silero strip these markers before synthesis. Unknown names such as
  `[dragon]` are preserved because they can be Ren'Py substitutions, just like `[score]`.
- To preserve a manual translation, set `manual_override`, provide `translated_text`, and set the line's `target_lang` to the requested language. An empty `target_lang` causes the batch to translate the line again when a target is requested.
- A character's assigned `line.voice_id` takes precedence over CLI `--voice`. The CLI voice applies to lines without an assigned voice.

## 🖥️ Hardware Requirements

| Component | Minimum | Recommended | Ideal |
|-----------|---------|-------------|-------|
| RAM | 8GB | 16GB | 32GB |
| GPU | Any | 6GB VRAM | 12GB+ VRAM |
| Disk | 5GB free | 20GB free | 50GB+ free |

## 🔐 Privacy

**We do NOT collect:**
- ❌ Personal data
- ❌ IP/MAC addresses
- ❌ Game files
- ❌ Browser history
- ❌ Any telemetry

**Everything stays on your device.**

See [PRIVACY.md](PRIVACY.md) for details.

## ⚖️ Legal

This is a **modding tool**. We do not distribute game content or clone real actors' voices.

- Users are responsible for uploaded voice samples
- Generated mods are for personal/non-commercial use
- See [DISCLAIMER.md](DISCLAIMER.md) for full details

## 📄 License

Apache 2.0 — Free to use, modify, and distribute.

## 💖 Support Development

This project is completely free. If you'd like to support development:

- 🇷🇺 [Boosty](https://boosty.to/YOUR_PAGE)
- 🌍 [Patreon](https://patreon.com/YOUR_PAGE)
- ☕ [Ko-fi](https://ko-fi.com/YOUR_PAGE)

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📚 Documentation

- [Getting Started](docs/getting_started.md)
- [Installation Guide](docs/installation.md)
- [User Guide](docs/user_guide.md)
- [Plugin Development](docs/plugin_development.md)
- [FAQ](docs/faq.md)

## 🗺️ Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features.

## ⭐ Star History

If this project helps you, please star it! ⭐

---

*Made with ❤️ for the modding community*
