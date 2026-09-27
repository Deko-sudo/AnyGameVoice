"""Base AI provider."""

class BaseProvider:
    """Provider interface."""

    def complete(self, prompt: str) -> str:
        """Complete (stub)."""
        raise NotImplementedError
