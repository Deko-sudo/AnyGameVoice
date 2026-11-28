"""UI tests (no server start, no network)."""

import os

import pytest


def test_index_exists():
    root = os.path.join(os.path.dirname(__file__), "..", "ui", "index.html")
    assert os.path.isfile(root)
    with open(root, encoding="utf-8") as fh:
        html = fh.read()
    assert 'id="appearance-dialog"' in html and "/assets/studio.js" in html


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


def test_rust_controls_are_served_with_wasm_policy():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from app.ui_server import create_app

    with TestClient(create_app()) as client:
        index = client.get("/")
        assert index.status_code == 200
        assert "/assets/rust-ui-loader.js" in index.text
        assert "'wasm-unsafe-eval'" in index.headers["content-security-policy"]
        wasm = client.get("/assets/rust-ui/anygamevoice_ui_bg.wasm")
        assert wasm.status_code == 200
        assert wasm.content.startswith(b"\x00asm")
        assert wasm.headers["content-type"].startswith("application/wasm")
