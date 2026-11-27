"""Local web UI server (Phase 2).

FastAPI app serving ui/index.html + JSON API. Runs fully offline
(except optional cloud providers the user configures themselves).

Endpoints:
  GET  /              -> index.html
  GET  /api/health    -> {"status": "ok"}
  POST /api/scan      -> {path} => hardware + access + folder scan
  POST /api/extract   -> {path, limit?} => dialogue lines
  GET  /api/voices    -> voice presets
  POST /api/mod       -> {path, out, ...} => background job {job_id}
  GET  /api/mod/{id}  -> job status
"""

import itertools
import threading
from pathlib import Path

from app.utils.paths import resource_path

INDEX = resource_path("ui", "index.html")

__all__ = ["create_app", "start_mod_job", "mod_job_status"]

_JOBS: dict = {}
_JOB_SEQ = itertools.count(1)
_JOBS_LOCK = threading.Lock()


def start_mod_job(params: dict) -> int:
    """Run cmd_mod in a background thread. Returns job id (testable, no HTTP)."""
    from app.main import cmd_mod

    if params.get("base_url"):
        from app.core.cloud_providers import _custom_url
        _custom_url(params["base_url"], "")
    public_fields = ("path", "out", "voice", "engine", "workers", "emotion", "translate_to",
                     "provider", "source_lang", "translation_model", "base_url")
    job_id = next(_JOB_SEQ)
    with _JOBS_LOCK:
        _JOBS[job_id] = {"id": job_id, "status": "running", "params": {k: params[k] for k in public_fields if k in params}, "error": ""}
    def _run():
        try:
            report = cmd_mod(
                params.get("path", ""),
                params.get("out", "./out"),
                voice=params.get("voice", ""),
                engine=params.get("engine", "piper"),
                workers=int(params.get("workers", 2)),
                emotion=params.get("emotion", "neutral"),
                translate_to=params.get("translate_to", ""),
                provider=params.get("provider", "ollama"),
                source_lang=params.get("source_lang", "auto"),
                translation_model=params.get("translation_model", ""),
                api_key=params.get("api_key", ""), base_url=params.get("base_url", ""),
            )
        except Exception as exc:  # noqa: BLE001 - surfaced via status
            with _JOBS_LOCK:
                _JOBS[job_id].update(status="failed", error=str(exc)[:500])
        else:
            with _JOBS_LOCK:
                _JOBS[job_id].update(report)

    threading.Thread(target=_run, daemon=True, name=f"agv-mod-{job_id}").start()
    return job_id


def mod_job_status(job_id: int) -> dict:
    """Snapshot of a mod job. Raises KeyError for unknown ids."""
    with _JOBS_LOCK:
        return dict(_JOBS[job_id])


def create_app():
    """Build the FastAPI application (imports are lazy for clear errors)."""
    try:
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise RuntimeError(
            "Web UI needs fastapi. Run: pip install -r requirements.txt"
        ) from exc

    from app.studio.ui_server import create_app as create_studio

    app = create_studio()

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

    @app.post("/api/mod")
    def api_mod(payload: dict):
        payload = payload or {}
        if not payload.get("path") or not payload.get("out"):
            return JSONResponse({"error": "path and out are required"}, status_code=400)
        return {"job_id": start_mod_job(payload)}

    @app.get("/api/mod/{job_id}")
    def api_mod_status(job_id: int):
        try:
            return mod_job_status(job_id)
        except KeyError:
            return JSONResponse({"error": "unknown job"}, status_code=404)

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
