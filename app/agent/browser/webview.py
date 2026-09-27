"""Webview helper (open pages in the system browser)."""

import webbrowser

__all__ = ["open_page"]


def open_page(url: str) -> bool:
    """Open a URL in the default browser. Returns True if attempted."""
    if not url or not url.startswith(("http://", "https://")):
        raise ValueError(f"Refusing to open non-HTTP URL: {url!r}")
    return webbrowser.open(url)
