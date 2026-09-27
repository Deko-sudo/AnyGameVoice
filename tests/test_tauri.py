"""Tauri scaffold + mod-job API tests (offline, no server start)."""

import json
import os
import time

REPO = os.path.join(os.path.dirname(__file__), "..")


def test_tauri_conf():
    path = os.path.join(REPO, "src-tauri", "tauri.conf.json")
    with open(path, encoding="utf-8") as fh:
        conf = json.load(fh)
    assert conf["productName"] == "AnyGameVoice"
    assert conf["build"]["devUrl"] == "http://127.0.0.1:8000"
    frontend = os.path.normpath(os.path.join(REPO, "src-tauri", conf["build"]["frontendDist"]))
    assert os.path.isfile(os.path.join(frontend, "index.html")), "frontendDist must contain the SPA"
    assert os.path.isfile(os.path.join(REPO, "src-tauri", "src", "main.rs"))
    with open(os.path.join(REPO, "src-tauri", "src", "main.rs"), encoding="utf-8") as fh:
        rs = fh.read()
    assert "spawn_backend" in rs and "RunEvent::Exit" in rs
    cap = os.path.join(REPO, "src-tauri", "capabilities", "default.json")
    with open(cap, encoding="utf-8") as fh:
        json.load(fh)  # must parse


def test_mod_job_lifecycle(tmp_path):
    from app import ui_server

    calls = []

    def fake_mod(path, out, **kwargs):
        calls.append((path, out, kwargs))
        with open(os.path.join(tmp_path, "ok.txt"), "w") as fh:
            fh.write("done")

    import app.main as mainmod

    orig = mainmod.cmd_mod
    mainmod.cmd_mod = fake_mod
    try:
        jid = ui_server.start_mod_job({"path": "game", "out": str(tmp_path), "engine": "piper"})
        deadline = time.time() + 10
        while ui_server.mod_job_status(jid)["status"] == "running" and time.time() < deadline:
            time.sleep(0.02)
        snap = ui_server.mod_job_status(jid)
    finally:
        mainmod.cmd_mod = orig
    assert snap["status"] == "done", snap
    assert calls and calls[0][0] == "game"


def test_mod_job_failure():
    from app import ui_server

    import app.main as mainmod

    def boom(*a, **k):
        raise ValueError("nope")

    orig = mainmod.cmd_mod
    mainmod.cmd_mod = boom
    try:
        jid = ui_server.start_mod_job({"path": "x", "out": "y"})
        deadline = time.time() + 10
        while ui_server.mod_job_status(jid)["status"] == "running" and time.time() < deadline:
            time.sleep(0.02)
        snap = ui_server.mod_job_status(jid)
    finally:
        mainmod.cmd_mod = orig
    assert snap["status"] == "failed" and "nope" in snap["error"]


def test_mod_routes_registered():
    pytest = __import__("pytest")
    pytest.importorskip("fastapi")
    from app.ui_server import INDEX, create_app

    assert INDEX.is_file(), f"INDEX points nowhere: {INDEX}"
    paths = {getattr(r, "path", "") for r in create_app().routes}
    assert "/api/mod" in paths
    assert "/api/mod/{job_id}" in paths
