"""XTTS engine (optional backend).

Needs the `TTS` package (coqui): pip install TTS
Voice cloning from a short reference sample.
"""

from .base import BaseTTSEngine

__all__ = ["XTTSEngine"]


class XTTSEngine(BaseTTSEngine):
    """XTTS v2 adapter (lazy import, GPU recommended)."""

    name = "xtts"

    def __init__(self, model: str = "tts_models/multilingual/multi-dataset/xtts_v2") -> None:
        self.model = model
        self._tts = None

    def is_available(self) -> bool:
        """True if the TTS package is importable."""
        try:
            import TTS  # noqa: F401

            return True
        except ImportError:
            return False

    def _load(self):
        if self._tts is None:
            try:
                from TTS.api import TTS
            except ImportError as exc:
                raise RuntimeError(
                    "XTTS needs the 'TTS' package. Run: pip install TTS"
                ) from exc
            self._tts = TTS(self.model)
        return self._tts

    def synthesize(self, text: str, voice: str = "") -> bytes:
        """Synthesize with voice cloning (voice = reference wav path)."""
        import tempfile, os

        tts = self._load()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out = tmp.name
        try:
            kwargs = {"text": text, "file_path": out}
            if voice:
                kwargs["speaker_wav"] = voice
                kwargs["language"] = "en"
            tts.tts_to_file(**kwargs)
            with open(out, "rb") as fh:
                return fh.read()
        finally:
            try:
                os.unlink(out)
            except OSError:
                pass
