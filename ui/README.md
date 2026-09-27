# UI

Local-first web interface (Phase 2).

## Run

```bash
pip install -r requirements.txt
python app/main.py ui 8000
# open http://127.0.0.1:8000
```

## Files

- `index.html` — single-file SPA, no CDN, works offline. Drag & drop
  (file-name preview; browsers hide real paths, so type the folder path),
  Scan / Extract / Voices buttons calling the API below.
- `../app/ui_server.py` — FastAPI app: `GET /`, `GET /api/health`,
  `POST /api/scan`, `POST /api/extract`, `GET /api/voices`.

Native desktop shell (Tauri) is a possible later step; the web UI
already covers the whole Phase-1 pipeline.
