"""TTS generator.

Routes text to the configured engine. Phase 1: piper only.
"""

from .engines.piper import PiperEngine

__all__ = ["generate_voice", "generate_voice_to_file"]

_ENGINES = {"piper": PiperEngine}


def _make_engine(name: str, voice: str = ""):
    cls = _ENGINES.get(name, PiperEngine)
    if cls is PiperEngine:
        return PiperEngine(model_path=voice)
    return cls()


def generate_voice(text: str, voice: str = "default", engine: str = "piper") -> bytes:
    """Generate voice audio bytes for text."""
    if not text or not text.strip():
        raise ValueError("text must not be empty")
    return _make_engine(engine, voice).synthesize(text, voice)


def generate_voice_to_file(text: str, out_path: str, voice: str = "", engine: str = "piper") -> str:
    """Generate audio and write to out_path. Returns out_path."""
    data = generate_voice(text, voice=voice, engine=engine)
    with open(out_path, "wb") as fh:
        fh.write(data)
    return out_path
