# Getting Started

## 1. Install

```bash
git clone https://github.com/Deko-sudo/AnyGameVoice.git
cd AnyGameVoice
pip install -r requirements.txt
python app/main.py
```

See [installation](installation.md) for optional components (Piper binary, GPU backends).

## 2. Scan your game

```bash
python app/main.py scan "C:\Games\MyRenpyGame"
```

This prints hardware recommendations, folder access, detected engine,
script files and audio inventory. Nothing is modified.

## 3. Extract dialogue

```bash
python app/main.py extract "C:\Games\MyRenpyGame"
```

Supported: Ren'Py (`.rpy`), RPG Maker (`data/Map*.json`), Godot (`.dialogue`).
Unity/Unreal compiled assets list audio files but need unpacked assets for text.

## 4. Generate voices (batch)

Get a Piper voice model first:

```bash
python scripts/download_models.py
```

Then:

```bash
python app/main.py mod "C:\Games\MyRenpyGame" --out ./out --voice ./models/en_US-lessac-medium.onnx
```

You get one `.wav` per line plus `dialogue.srt`. Original game files are
never touched by this step; use the replacer API/UI to install audio with
automatic timestamped backups.

## 5. Web UI

```bash
python app/main.py ui 8000
# open http://127.0.0.1:8000
```

Next: [User Guide](user_guide.md).
