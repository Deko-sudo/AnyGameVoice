"""Base AI provider.

All providers talk to their HTTP API directly with `requests`
(no heavy SDKs). Keys come from env/.env, never stored anywhere else.
"""

import os

__all__ = ["BaseProvider"]


class BaseProvider:
    """Provider interface."""

    name: str = "base"
    env_key: str = ""
    default_model: str = ""

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self.api_key = api_key or (os.environ.get(self.env_key, "") if self.env_key else "")
        self.model = model or self.default_model

    def _post_json(self, url: str, payload: dict, headers: dict | None = None, timeout: int = 60) -> dict:
        """POST JSON and return parsed response. Raises RuntimeError on failure."""
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("AI providers need 'requests'. Run: pip install -r requirements.txt") from exc
        try:
            resp = requests.post(url, json=payload, headers=headers or {}, timeout=timeout)
        except Exception as exc:
            raise RuntimeError(f"{self.name} request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise RuntimeError(f"{self.name} HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeError(f"{self.name}: invalid JSON response") from exc
        return data if isinstance(data, dict) else {}

    def _require_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                f"{self.name} needs an API key. Set {self.env_key} in .env "
                "(see .env.example). Ollama works without a key."
            )

    def complete(self, prompt: str, system: str = "") -> str:
        """Return assistant text for prompt. Must be overridden."""
        raise NotImplementedError
