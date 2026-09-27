"""Silero engine (optional backend).

Needs `torch` + `torchaudio`: pip install torch torchaudio
Lightweight, fast on CPU, good default when no GPU.
"""

from .base import BaseTTSEngine

__all__ = ["SileroEngine"]


class SileroEngine(BaseTTSEngine):
    """Silero TTS adapter (lazy import)."""

    name = "silero"

    def __init__(self, model: str = "", speaker: str = "en_0") -> None:
        self.model = model
        self.speaker = speaker
        self._model = None

    def is_available(self) -> bool:
        """True if torch is importable."""
        try:
            import torch  # noqa: F401

            return True
        except ImportError:
            return False

    def _load(self):
        if self._model is None:
            try:
                import torch
            except ImportError as exc:
                raise RuntimeError(
                    "Silero needs 'torch' + 'torchaudio'. Run: pip install torch torchaudio"
                ) from exc
            self._model, _ = torch.hub.load(
                "snakers4/silero-models", "silero_tts", language="en", speaker="v3_en"
            )
        return self._model

    def synthesize(self, text: str, voice: str = "") -> bytes:
        """Synthesize wav bytes via silero."""
        import io

        model = self._load()
        audio = model.apply_tts(text, speaker=voice or self.speaker, sample_rate=48000)
        import soundfile as sf

        buf = io.BytesIO()
        sf.write(buf, audio.numpy(), 48000, format="WAV")
        return buf.getvalue()
