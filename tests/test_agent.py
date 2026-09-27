"""Agent tests (offline: network calls mocked)."""

from unittest.mock import MagicMock, patch

import pytest


def test_search_needs_key():
    from app.agent.search.brave_search import BraveSearch
    from app.agent.search.tavily_search import TavilySearch

    with pytest.raises(RuntimeError):
        TavilySearch(api_key="").search("x")
    with pytest.raises(RuntimeError):
        BraveSearch(api_key="").search("x")


def test_tavily_parses_results():
    from app.agent.search.tavily_search import TavilySearch

    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"results": [{"title": "T", "url": "http://x", "content": "snippet"}]}
    with patch("requests.post", return_value=m):
        out = TavilySearch(api_key="k").search("q")
    assert out == [{"title": "T", "url": "http://x", "snippet": "snippet"}]


def test_parse_page():
    pytest.importorskip("bs4")
    from app.agent.parser.page_parser import parse_page

    html = "<html><head><title>t</title></head><body><script>var x=1;</script><p>Hello <b>world</b></p></body></html>"
    assert "Hello world" in parse_page(html)


def test_research_flow():
    from app.agent.ai_agent import AIAgent

    agent = AIAgent(provider="ollama", search="tavily", api_key="k", search_key="k")
    fake_search = MagicMock()
    fake_search.search.return_value = [{"title": "T", "url": "http://x", "snippet": "s"}]
    fake_provider = MagicMock()
    fake_provider.complete.return_value = "summary"
    with (
        patch.object(AIAgent, "_make_search", return_value=fake_search),
        patch.object(AIAgent, "_make_provider", return_value=fake_provider),
        patch("app.agent.ai_agent.fetch_page", return_value="<p>page text</p>"),
    ):
        out = agent.research("piper voices")
    assert out["summary"] == "summary"
    assert out["sources"][0]["url"] == "http://x"
    assert "text" in out["sources"][0]


def test_webview_rejects_bad_url():
    from app.agent.browser.webview import open_page

    with pytest.raises(ValueError):
        open_page("file:///etc/passwd")
