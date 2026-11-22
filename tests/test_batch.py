"""Subtitle + batch pipeline tests."""

import io
import wave
from unittest.mock import patch


def _line(speaker, text):
    from app.models.dialogue import Dialogue

    return Dialogue(speaker=speaker, text=text)


def test_srt_format():
    from app.utils.audio_utils import estimate_duration, fmt_timestamp, to_srt, to_vtt

    assert fmt_timestamp(0) == "00:00:00,000"
    assert fmt_timestamp(61.5) == "00:01:01,500"
    assert fmt_timestamp(61.5, vtt=True) == "00:01:01.500"
    assert estimate_duration("") == 1.0
    srt = to_srt([_line("e", "Hello!"), _line("narrator", "Wind blows.")])
    assert "1\n00:00:00,000 --> " in srt
    assert "<v e>Hello!" in srt
    assert "Wind blows." in srt  # narrator has no <v> tag
    vtt = to_vtt([_line("e", "Hi")])
    assert vtt.startswith("WEBVTT")


def test_batch_mod(tmp_path):
    from app.main import cmd_mod

    game = tmp_path / "game"
    (game / "game").mkdir(parents=True)
    (game / "game" / "script.rpy").write_text('e "Hello there!"\n"Wind."\n', encoding="utf-8")
    out = tmp_path / "out"

    def fake_gen(line, out_path, voice="", engine="piper", emotion="neutral"):
        with open(out_path, "wb") as fh:
            fh.write(b"FAKEWAV" + line.text.encode())
        return out_path

    # cmd_mod imports generate_voice_to_file lazily, so patch the source.
    with patch("app.core.tts.generator.generate_voice_to_file", side_effect=fake_gen):
        cmd_mod(str(game), str(out))
    wavs = sorted(out.glob("*.wav"))
    assert len(wavs) == 2
    assert (out / "dialogue.srt").is_file()


def test_translated_line_reaches_wav(tmp_path):
    from app.core.tts import generator
    from app.main import cmd_mod
    from app.models.line import Line

    game = tmp_path / "game"
    game.mkdir()
    (game / "script.rpy").write_text('e "Hi!"\n', encoding="utf-8")
    output = tmp_path / "out"
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        wav.writeframes(b"\0\0" * 80)

    with (
        patch("app.core.translate.translate_text", return_value="¡Hola!"),
        patch.object(generator, "get_engine") as engine,
        patch.object(generator, "generate_voice_to_file", wraps=generator.generate_voice_to_file) as write,
    ):
        engine.return_value.synthesize.return_value = audio.getvalue()
        cmd_mod(str(tmp_path), str(output), voice="sample", translate_to="es")

    line = write.call_args.args[0]
    assert isinstance(line, Line)
    assert (line.speaker, line.text, line.tts_text) == ("e", "¡Hola!", "¡Hola!")
    assert (line.engine_id, line.source_file, line.line_no) == ("renpy", "script.rpy", 1)
    assert (line.source_text, line.target_lang) == ("Hi!", "es")
    engine.return_value.synthesize.assert_called_once_with("¡Hola!", "sample", emotion="neutral")
    with wave.open(str(output / "0000_e.wav"), "rb") as wav:
        assert wav.getnframes() == 80


def test_mod_returns_report_while_tts_is_still_blocked(tmp_path, monkeypatch):
    import json
    import threading
    import time
    from pathlib import Path

    from app.core.queue import task_queue
    from app.core.tts import generator
    from app.main import cmd_mod

    game = tmp_path / "game"
    game.mkdir()
    (game / "script.rpy").write_text('e "Ready."\ne "Blocked."\ne "Pending."\n', encoding="utf-8")
    out = tmp_path / "out"
    started = threading.Event()
    release = threading.Event()
    queue = task_queue.TaskQueue(workers=1)
    shutdown = queue.shutdown

    def short_shutdown(wait, timeout):
        assert wait and timeout == 60
        assert started.wait(1)
        shutdown(wait=True, timeout=0.05)

    def synthesize(line, out_path, **kwargs):
        with Path(out_path).open("wb") as wav:
            if line.text == "Blocked.":
                started.set()
                release.wait(timeout=3)
            wav.write(line.text.encode())

    monkeypatch.setattr(task_queue, "TaskQueue", lambda workers: queue)
    monkeypatch.setattr(queue, "shutdown", short_shutdown)
    monkeypatch.setattr(generator, "generate_voice_to_file", synthesize)
    try:
        before = time.monotonic()
        report = cmd_mod(str(tmp_path), str(out), workers=1)
        assert time.monotonic() - before < 1.5
        assert (report["status"], report["succeeded"], report["failed"], report["total"]) == ("partial", 1, 2, 3)
        assert [row["skipped_reason"] for row in report["lines"]] == [None, "TTS timed out", "TTS timed out"]
        assert [path.name for path in out.glob("*.wav")] == ["0000_e.wav"]
        saved = (out / "report.json").read_bytes()
        assert json.loads(saved) == report
        assert "Blocked." not in (out / "dialogue.srt").read_text(encoding="utf-8")
        # A subsequent run may already own the final path when the old TTS returns.
        (out / "0001_e.wav").write_bytes(b"new run")
    finally:
        release.set()
        shutdown(wait=True)
    assert (out / "0001_e.wav").read_bytes() == b"new run"
    assert (out / "report.json").read_bytes() == saved
    assert not list(out.glob(".agv-*"))
