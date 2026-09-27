"""Base TTS engine."""

class BaseTTSEngine:
    """Base TTS interface."""

    def synthesize(self, text: str, voice: str) -> bytes:
        """Synthesize audio (stub)."""
        raise NotImplementedError
