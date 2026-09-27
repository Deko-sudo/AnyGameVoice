"""Brave search."""

from .base_search import BaseSearch

__all__ = ["BraveSearch"]


class BraveSearch(BaseSearch):
    """Brave Search API adapter."""

    env_key = "BRAVE_SEARCH_API_KEY"
    api_url = "https://api.search.brave.com/res/v1/web/search"

    def search(self, query: str, max_results: int = 5) -> list:
        """Search via Brave."""
        self._require_key()
        import requests

        resp = requests.get(
            self.api_url,
            params={"q": query, "count": max_results},
            headers={"X-Subscription-Token": self.api_key},
            timeout=30,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"brave HTTP {resp.status_code}: {resp.text[:200]}")
        items = resp.json().get("web", {}).get("results", [])
        return [
            {"title": it.get("title", ""), "url": it.get("url", ""), "snippet": it.get("description", "")[:500]}
            for it in items
            if isinstance(it, dict)
        ]
