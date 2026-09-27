"""UI tests (no server start, no network)."""

import os

import pytest


def test_index_exists():
    root = os.path.join(os.path.dirname(__file__), "..", "ui", "index.html")
    assert os.path.isfile(root)
    with open(root, encoding="utf-8") as fh:
        html = fh.read()
    assert "/api/scan" in html and "/api/extract" in html and "/api/voices" in html


def test_app_routes():
    fastapi = pytest.importorskip("fastapi")
    from app.ui_server import create_app

    app = create_app()
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/" in paths
    assert "/api/health" in paths
    assert "/api/scan" in paths
    assert "/api/extract" in paths
    assert "/api/voices" in paths
