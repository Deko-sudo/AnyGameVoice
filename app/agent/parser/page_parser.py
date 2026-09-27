"""Page parser (fetch + extract readable text)."""

__all__ = ["fetch_page", "parse_page"]


def fetch_page(url: str, timeout: int = 20) -> str:
    """Download a page and return raw HTML. Raises RuntimeError on failure."""
    import requests

    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "AnyGameVoice/0.1"})
    except Exception as exc:
        raise RuntimeError(f"fetch failed: {exc}") from exc
    if resp.status_code >= 400:
        raise RuntimeError(f"fetch HTTP {resp.status_code}: {url}")
    return resp.text


def parse_page(html: str, max_chars: int = 4000) -> str:
    """Extract readable text from HTML."""
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("Page parsing needs 'beautifulsoup4'. Run: pip install -r requirements.txt") from exc
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    return text[:max_chars]
