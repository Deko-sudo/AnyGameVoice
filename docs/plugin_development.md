# Plugin Development

Engine support = two functions in `app/core/game_detector/engines/<id>.py`:

```python
from app.core.extractor.models import ExtractedLine

def extract_<id>_folder(game_path: str) -> list[ExtractedLine]: ...
```

`ExtractedLine` fields: `speaker`, `text`, `source_file`, `line_no`, `metadata`.

## Steps

1. Copy `plugins/examples/sample_plugin.py` as a starting sketch.
2. Implement detection markers in `detector.py::ENGINE_MARKERS`
   (`"<id>": ("marker1", "dir/*.ext")`, globs relative to game root).
3. Implement `extract_<id>_folder` (+ `_file` helper). Tolerate messy
   real-world files: catch `OSError`/`ValueError`, skip nulls.
4. Route it in `extract_dialogue()` + `supported_engines()`.
5. Add `tests/test_engines.py` cases with fake folders in `tmp_path`.
6. If the format is compiled (bundles/paks), implement
   `list_audio_assets(game_path, limit=200)` instead and return `[]`
   from the extractor with a docstring saying why (see `unity.py`).

## Conventions

- No network, no heavy deps in extractors (stdlib only).
- Never write into the game folder; extraction is read-only.
- Type hints + docstrings (flake8/mypy run in CI, non-blocking).
