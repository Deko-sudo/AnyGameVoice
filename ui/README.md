# Local studio

Run `python app/main.py ui 8000` and open http://127.0.0.1:8000.
See [the user guide](../docs/user_guide.md) for supported games and automatic setup.

`studio.js` owns project state and generation; `automatic.js` handles automatic
selection and jobs; `setup-components.js` handles explicit component installation
and restoring its progress after a page reload. The UI has no CDN dependencies.

The normal launch opens this studio on port 8000. Studio requests use the /api/studio prefix. Existing CLI and /api/mod clients keep their Phase 1.5 report and manifest formats.

Component setup API:

- `POST /api/studio/setup/plan`: read-only availability, sizes, sources and licenses.
- `POST /api/studio/setup`: reviewed component IDs plus explicit `allow_downloads: true`.
- `GET /api/studio/setup/{id}`: progress/result; `POST /api/studio/setup/{id}/cancel`: cancellation.

Setup and synthesis/research/mod operations are mutually exclusive. Component
files persist in application data; task IDs do not survive a backend restart.
Voice/SDK downloads use a pinned catalog and SHA-256 validation.

The native Tauri shell is a separate development target; see [tauri.md](../docs/tauri.md).
