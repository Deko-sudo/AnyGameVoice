# Installation

## Requirements

- Python 3.10+ (3.10, 3.11, 3.12 tested in CI)
- 8GB RAM minimum, 16GB recommended
- Optional: NVIDIA GPU for XTTS/Bark

## Base install

```bash
git clone https://github.com/Deko-sudo/AnyGameVoice.git
cd AnyGameVoice
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
pip install -r requirements.txt
```

Or use the helper scripts: `scripts/setup.bat` (Windows), `scripts/setup.sh` (Linux/macOS).

## Optional components

| Component | Install | Used for |
|-----------|---------|----------|
| Piper TTS binary | https://github.com/rhasspy/piper/releases | Fast local TTS (default engine) |
| Piper voice model | `python scripts/download_models.py` | `en_US-lessac-medium.onnx` (~60MB) into `models/` |
| ffmpeg | https://ffmpeg.org/download.html | Audio conversion (replacer, non-wav assets) |
| Coqui XTTS | `pip install TTS` | Voice cloning, needs 6GB+ VRAM |
| Bark | `pip install suno-bark scipy` | Expressive lines, slow on CPU |
| Silero | `pip install torch torchaudio soundfile` | Lightweight CPU TTS |

Engines check their own availability: `python -c "from app.core.tts.generator import list_engines; print(list_engines())"`.

## Verify

```bash
pytest tests/ -q
python app/main.py
```
