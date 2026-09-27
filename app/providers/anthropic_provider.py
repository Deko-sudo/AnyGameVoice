"""Anthropic provider (Messages API)."""

from .base import BaseProvider

__all__ = ["AnthropicProvider"]


class AnthropicProvider(BaseProvider):
    """Anthropic Claude adapter."""

    name = "anthropic"
    env_key = "ANTHROPIC_API_KEY"
    default_model = "claude-3-5-haiku-latest"
    api_url = "https://api.anthropic.com/v1/messages"

    def complete(self, prompt: str, system: str = "") -> str:
        """Complete via Messages API."""
        self._require_key()
        payload = {"model": self.model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}
        if system:
            payload["system"] = system
        data = self._post_json(
            self.api_url,
            payload,
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
        )
        try:
            blocks = data["content"]
            return "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"{self.name}: unexpected response shape") from exc
