"""TTS generator (Phase 4).

Routes text to the configured engine via a registry.
Only piper works out of the box; xtts/bark/silero need optional
packages and raise a clear RuntimeError otherwise.
"""

import inspect
from pathlib import Path

from app.core.tts.engines.bark import BarkEngine
from app.studio.core.tts.engines.piper import PiperEngine
from app.core.tts.engines.silero import SileroEngine
from app.studio.core.tts.engines.xtts import XTTSEngine

__all__ = ["generate_voice", "generate_voice_to_file", "list_engines", "get_engine", "validate_synthesis"]

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


def validate_synthesis(engine: str, voice: str = "") -> None:
    """Fail before queueing work if the backend or model is missing."""
    eng = get_engine(engine, voice)
    if engine == "piper":
        model = Path(voice).expanduser()
        if not voice or not model.is_file():
            raise FileNotFoundError("Choose a Piper .onnx model before generating audio.")
        if not Path(str(model) + ".json").is_file():
            raise FileNotFoundError("Piper also needs the matching .onnx.json file beside the model.")
    elif engine == "xtts":
        from app.core.tts.reference import validate_reference
        validate_reference(voice)
    if not eng.is_available():
        raise RuntimeError(f"TTS backend '{engine}' is not installed. See docs/installation.md.")


def generate_voice(text: str, voice: str = "default", engine: str = "piper", emotion: str = "neutral", language: str = "en", *,
                   blend: tuple[str, float] | None = None) -> bytes:
    """Generate voice audio bytes for text (emotion tag or param)."""
    if not text or not text.strip():
        raise ValueError("text must not be empty")
    if engine == "piper" and (not voice or voice == "default"):
        raise FileNotFoundError(
            "Piper needs a voice model (.onnx). "
            "Run scripts/download_models.py or pass voice=/path/to/model.onnx"
        )
    if voice and engine in {"piper", "xtts"}:
        voice = str(Path(voice).expanduser())
    if engine == "silero" and language != "en":
        raise ValueError("The current Silero adapter supports English only.")
    eng = get_engine(engine, voice)
    from app.studio.core.tts.emotions import apply_emotion
    parameters = inspect.signature(eng.synthesize).parameters
    kwargs = {}
    if "emotion" in parameters:
        kwargs["emotion"] = emotion
    else:
        text, _ = apply_emotion(engine, text)
    if "language" in parameters:
        kwargs["language"] = language
    if blend is not None:
        if "blend" not in parameters:
            raise ValueError("Выбранный движок не поддерживает ограничение переноса тембра.")
        kwargs["blend"] = blend
    return eng.synthesize(text, voice, **kwargs)


def generate_voice_to_file(text: str, out_path: str, voice: str = "", engine: str = "piper", emotion: str = "neutral", language: str = "en", *,
                           blend: tuple[str, float] | None = None) -> str:
    """Generate audio and write to out_path. Returns out_path."""
    data = generate_voice(text, voice=voice, engine=engine, emotion=emotion, language=language, blend=blend)
    with open(out_path, "wb") as fh:
        fh.write(data)
    return out_path
