"""Built-in AI agent (Phase 6).

research(topic): search the web -> fetch top pages -> summarize
with the configured AI provider. Used for things like finding
voice model download links or engine modding docs.
"""

from .parser.page_parser import fetch_page, parse_page

__all__ = ["AIAgent"]


class AIAgent:
    """Agent entry point (search + provider)."""

    def __init__(self, provider: str = "ollama", search: str = "tavily", **kwargs) -> None:
        self.provider_name = provider
        self.search_name = search
        self.kwargs = kwargs

    def _make_search(self):
        if self.search_name == "brave":
            from .search.brave_search import BraveSearch

            return BraveSearch(api_key=self.kwargs.get("search_key", ""))
        from .search.tavily_search import TavilySearch

        return TavilySearch(api_key=self.kwargs.get("search_key", ""))

    def _make_provider(self):
        from app.providers.router import get_provider

        return get_provider(self.provider_name, api_key=self.kwargs.get("api_key", ""))

    def research(self, topic: str, max_pages: int = 3) -> dict:
        """Research a topic. Returns {topic, sources, summary}."""
        search = self._make_search()
        results = search.search(topic, max_results=max_pages)
        sources = []
        for item in results[:max_pages]:
            try:
                text = parse_page(fetch_page(item["url"]))
            except RuntimeError as exc:
                text = f"(unavailable: {exc})"
            sources.append({**item, "text": text[:2000]})
        context = "\n\n".join(f"- {s['title']} ({s['url']}): {s['text'][:500]}" for s in sources)
        provider = self._make_provider()
        summary = provider.complete(
            f"Research notes:\n{context}",
            system=f"Summarize research about: {topic}. Be concise, cite URLs.",
        )
        return {"topic": topic, "sources": sources, "summary": summary}
