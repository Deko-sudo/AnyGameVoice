"""Base TTS engine."""

__all__ = ["BaseTTSEngine"]


class BaseTTSEngine:
    """Base TTS interface. All engines are local-first."""

    name: str = "base"

    def is_available(self) -> bool:
        """True if the engine backend is installed and usable."""
        return False

    def synthesize(self, text: str, voice: str = "") -> bytes:
        """Synthesize wav bytes for text. Must be overridden."""
        raise NotImplementedError
