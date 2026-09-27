"""Base search."""

import os

__all__ = ["BaseSearch"]


class BaseSearch:
    """Search interface. Returns [{title, url, snippet}]."""

    env_key: str = ""

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key or (os.environ.get(self.env_key, "") if self.env_key else "")

    def _require_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(f"Search needs an API key. Set {self.env_key} in .env.")

    def search(self, query: str, max_results: int = 5) -> list:
        """Search (stub)."""
        raise NotImplementedError
