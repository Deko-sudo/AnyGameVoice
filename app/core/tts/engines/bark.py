"""Bark engine (optional backend).

Needs `suno-bark`: pip install suno-bark
Good for expressive / non-verbal sounds. Slow on CPU.
"""

from .base import BaseTTSEngine

__all__ = ["BarkEngine"]


class BarkEngine(BaseTTSEngine):
    """Bark adapter (lazy import)."""

    name = "bark"

    def is_available(self) -> bool:
        """True if bark is importable."""
        try:
            import bark  # noqa: F401

            return True
        except ImportError:
            return False

    def synthesize(self, text: str, voice: str = "") -> bytes:
        """Synthesize wav bytes via bark."""
        try:
            import io

            import numpy as np
            from bark import SAMPLE_RATE, generate_audio
            from scipy.io.wavfile import write as wav_write
        except ImportError as exc:
            raise RuntimeError(
                "Bark needs 'suno-bark', 'scipy'. Run: pip install suno-bark scipy"
            ) from exc
        audio = generate_audio(text, history_prompt=voice or None)
        buf = io.BytesIO()
        wav_write(buf, SAMPLE_RATE, (np.array(audio) * 32767).astype(np.int16))
        return buf.getvalue()
