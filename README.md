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
