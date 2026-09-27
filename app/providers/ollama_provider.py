"""Ollama provider (local, no key needed)."""

import os

from .base import BaseProvider

__all__ = ["OllamaProvider"]


class OllamaProvider(BaseProvider):
    """Local Ollama adapter (http://localhost:11434 by default)."""

    name = "ollama"
    env_key = ""
    default_model = "llama3.1"

    def __init__(self, api_key: str = "", model: str = "", base_url: str = "") -> None:
        super().__init__(api_key=api_key, model=model)
        self.base_url = base_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")

    def complete(self, prompt: str, system: str = "") -> str:
        """Complete via /api/chat (non-streaming)."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        data = self._post_json(
            f"{self.base_url.rstrip('/')}/api/chat",
            {"model": self.model, "messages": messages, "stream": False},
        )
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"{self.name}: unexpected response shape") from exc
