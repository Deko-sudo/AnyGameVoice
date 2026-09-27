"""Local web UI server (Phase 2).

FastAPI app serving ui/index.html + JSON API. Runs fully offline
(except optional cloud providers the user configures themselves).

Endpoints:
  GET  /              -> index.html
  GET  /api/health    -> {"status": "ok"}
  POST /api/scan      -> {path} => hardware + access + folder scan
  POST /api/extract   -> {path, limit?} => dialogue lines
  GET  /api/voices    -> voice presets
"""

from pathlib import Path

INDEX = Path(__file__).resolve().parent / "index.html"

__all__ = ["create_app"]


def create_app():
    """Build the FastAPI application (imports are lazy for clear errors)."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import FileResponse, JSONResponse
    except ImportError as exc:
        raise RuntimeError(
            "Web UI needs fastapi. Run: pip install -r requirements.txt"
        ) from exc

    app = FastAPI(title="AnyGameVoice", version="0.1.0")

    @app.get("/")
    def index():
        return FileResponse(INDEX)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/scan")
    def api_scan(payload: dict):
        from app.core.game_detector.detector import scan_game_folder
        from app.core.scanner.hardware import recommend_settings, scan_hardware
        from app.core.scanner.permissions import check_path_access

        path = (payload or {}).get("path", "")
        hw = scan_hardware()
        result = {
            "hardware": hw,
            "recommend": recommend_settings(hw),
            "access": check_path_access(path),
        }
        if result["access"]["exists"]:
            result["folder"] = scan_game_folder(path)
        return JSONResponse(result)

    @app.post("/api/extract")
    def api_extract(payload: dict):
        from app.core.extractor.dialogue_extractor import extract_dialogue

        payload = payload or {}
        lines = extract_dialogue(payload.get("path", ""))
        limit = int(payload.get("limit", 100))
        items = [
            {
                "speaker": ln.speaker,
                "text": ln.text,
                "source_file": ln.source_file,
                "line_no": ln.line_no,
            }
            for ln in lines[:limit]
        ]
        return {"total": len(lines), "lines": items}

    @app.get("/api/voices")
    def api_voices():
        from app.core.tts.voice_manager import VoiceManager

        voices = VoiceManager().list_voices()
        return {
            "voices": [
                {"name": v.name, "path": v.path, "engine": v.engine} for v in voices
            ]
        }

    return app


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the UI with uvicorn (blocking)."""
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "Web UI needs uvicorn. Run: pip install -r requirements.txt"
        ) from exc
    uvicorn.run(create_app(), host=host, port=port)
