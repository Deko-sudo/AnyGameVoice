"""OpenAI-compatible chat helper shared by openai/groq/mistral/deepseek."""

from .base import BaseProvider

__all__ = ["OpenAICompatibleProvider"]


class OpenAICompatibleProvider(BaseProvider):
    """Chat Completions API: {url} with Bearer key."""

    api_url: str = ""

    def complete(self, prompt: str, system: str = "") -> str:
        """Complete via Chat Completions."""
        self._require_key()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        data = self._post_json(
            self.api_url,
            {"model": self.model, "messages": messages},
            {"Authorization": f"Bearer {self.api_key}"},
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"{self.name}: unexpected response shape") from exc


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI adapter."""

    name = "openai"
    env_key = "OPENAI_API_KEY"
    default_model = "gpt-4o-mini"
    api_url = "https://api.openai.com/v1/chat/completions"
