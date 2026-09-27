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
  `POST /api/scan`, `POST /api/extract`, `GET /api/voices`,
  `POST /api/mod` + `GET /api/mod/{id}` (background mod jobs with
  engine/emotion/translation options).
- The "Generate mod" panel starts a job and polls its status.

Desktop shell: see `docs/tauri.md` (`src-tauri/` wraps this UI
in a native window; the web UI also runs standalone).

Native desktop shell (Tauri) is a possible later step; the web UI
already covers the whole Phase-1 pipeline.
