"""Terminal API status and the report on disk describe the same batch."""

import json
import time
import wave

import pytest

from app import ui_server
from app.core.tts import generator


@pytest.mark.parametrize(
    ("texts", "broken", "expected"),
    [
        (["First.", "Second."], {"Second."}, "partial"),
        (["Only."], {"Only."}, "failed"),
        ([], set(), "failed"),
        (["Only."], set(), "done"),
    ],
)
def test_mod_job_reports_every_line(tmp_path, monkeypatch, texts, broken, expected):
    game = tmp_path / "game"
    game.mkdir()
    (game / "script.rpy").write_text(
        "".join(f'e "{text}"\n' for text in texts), encoding="utf-8",
    )
    out = tmp_path / "out"

    def synthesize(line, out_path, **kwargs):
        if line.text in broken:
            raise RuntimeError("test voice unavailable")
        with wave.open(out_path, "wb") as wav:
            wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            wav.writeframes(b"\0\0")
        return out_path

    monkeypatch.setattr(generator, "generate_voice_to_file", synthesize)
    job = ui_server.start_mod_job({"path": str(tmp_path), "out": str(out)})
    deadline = time.monotonic() + 5
    snapshot = ui_server.mod_job_status(job)
    while snapshot["status"] == "running" and time.monotonic() < deadline:
        time.sleep(0.01)
        snapshot = ui_server.mod_job_status(job)

    assert snapshot["status"] == expected
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert {key: snapshot[key] for key in report} == report
    assert (report["succeeded"], report["failed"], report["total"]) == (
        len(texts) - len(broken), len(broken), len(texts),
    )
    assert len(report["lines"]) == len(texts)
    subtitles = (out / "dialogue.srt").read_text(encoding="utf-8")
    for i, (row, text) in enumerate(zip(report["lines"], texts)):
        assert (row["index"], row["source_file"], row["line_no"]) == (i, "script.rpy", i + 1)
        if text in broken:
            assert row["status"] == "failed"
            assert row["skipped_reason"] == "test voice unavailable"
            assert text not in subtitles
        else:
            assert row["status"] == "succeeded" and row["skipped_reason"] is None
            assert (out / row["wav"]).is_file() and text in subtitles
