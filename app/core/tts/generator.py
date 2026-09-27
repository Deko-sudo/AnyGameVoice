"""TTS generator (Phase 4).

Routes text to the configured engine via a registry.
Only piper works out of the box; xtts/bark/silero need optional
packages and raise a clear RuntimeError otherwise.
"""

from .engines.bark import BarkEngine
from .engines.piper import PiperEngine
from .engines.silero import SileroEngine
from .engines.xtts import XTTSEngine

__all__ = ["generate_voice", "generate_voice_to_file", "list_engines", "get_engine"]

ENGINES = {
    "piper": PiperEngine,
    "xtts": XTTSEngine,
    "bark": BarkEngine,
    "silero": SileroEngine,
}


def list_engines() -> dict:
    """Return {name: available} for all known engines."""
    return {name: cls().is_available() for name, cls in ENGINES.items()}


def get_engine(name: str, voice: str = ""):
    """Build an engine instance. Raises ValueError for unknown names."""
    cls = ENGINES.get(name)
    if cls is None:
        raise ValueError(f"Unknown TTS engine: {name}. Known: {sorted(ENGINES)}")
    if cls is PiperEngine:
        return PiperEngine(model_path=voice)
    return cls()


def generate_voice(text: str, voice: str = "default", engine: str = "piper") -> bytes:
    """Generate voice audio bytes for text."""
    if not text or not text.strip():
        raise ValueError("text must not be empty")
    if engine == "piper" and (not voice or voice == "default"):
        raise FileNotFoundError(
            "Piper needs a voice model (.onnx). "
            "Run scripts/download_models.py or pass voice=/path/to/model.onnx"
        )
    return get_engine(engine, voice).synthesize(text, voice)


def generate_voice_to_file(text: str, out_path: str, voice: str = "", engine: str = "piper") -> str:
    """Generate audio and write to out_path. Returns out_path."""
    data = generate_voice(text, voice=voice, engine=engine)
    with open(out_path, "wb") as fh:
        fh.write(data)
    return out_path
