"""Tavily search."""

from .base_search import BaseSearch

__all__ = ["TavilySearch"]


class TavilySearch(BaseSearch):
    """Tavily AI search adapter."""

    env_key = "TAVILY_API_KEY"
    api_url = "https://api.tavily.com/search"

    def search(self, query: str, max_results: int = 5) -> list:
        """Search via Tavily."""
        self._require_key()
        import requests

        resp = requests.post(
            self.api_url,
            json={"api_key": self.api_key, "query": query, "max_results": max_results},
            timeout=30,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"tavily HTTP {resp.status_code}: {resp.text[:200]}")
        items = resp.json().get("results", [])
        return [
            {"title": it.get("title", ""), "url": it.get("url", ""), "snippet": it.get("content", "")[:500]}
            for it in items
            if isinstance(it, dict)
        ]
