"""Emotion tests (offline)."""

import pytest


def test_parse_emotion():
    from app.core.tts.emotions import parse_emotion

    assert parse_emotion("[happy] Hello!") == ("happy", "Hello!")
    assert parse_emotion('<emotion="sad">Rain.') == ("sad", "Rain.")
    assert parse_emotion("Plain line.") == ("neutral", "Plain line.")
    assert parse_emotion("[dragon] Rawr") == ("neutral", "[dragon] Rawr")
    assert parse_emotion("[player_name]") == ("neutral", "[player_name]")
    assert parse_emotion("[score] points") == ("neutral", "[score] points")
    emo, clean = parse_emotion("[laughs] Ha ha")
    assert emo == "neutral" and "[laughs]" in clean  # bark-native marker kept


def test_substitution_inside_renpy_tag_survives_emotion_processing(tmp_path):
    from app.core.game_detector.engines.renpy import extract_renpy_file
    from app.core.tts.emotions import apply_emotion, parse_emotion

    script = tmp_path / "script.rpy"
    script.write_text('e "{b}[player_name]{/b}"\n', encoding="utf-8")
    line, = extract_renpy_file(str(script))
    assert parse_emotion(line.source_text) == ("neutral", "[player_name]")
    for engine in ("piper", "bark", "xtts", "silero"):
        text, _ = apply_emotion(engine, "[happy] [player_name] has [score] points")
        assert text == "[player_name] has [score] points"


def test_piper_flags():
    from app.core.tts.emotions import piper_flags

    assert piper_flags("neutral") == []
    assert piper_flags("bogus") == []
    flags = piper_flags("sad")
    assert "--length-scale" in flags and "1.15" in flags


def test_apply_emotion_bark_markers():
    from app.core.tts.emotions import apply_emotion

    clean, _ = apply_emotion("bark", "[happy] Hi [laughs]")
    assert "[happy]" not in clean and "[laughs]" in clean
    clean, _ = apply_emotion("xtts", "[angry] Quiet!")
    assert clean == "Quiet!"


@pytest.mark.parametrize(("engine", "text", "expected"), [
    ("piper", "[laughs] Ha ha", "Ha ha"),
    ("xtts", "[sighs] Ha", "Ha"),
    ("silero", "[dragon] Rawr", "[dragon] Rawr"),
    ("bark", "[laughs] Ha ha", "[laughs] Ha ha"),
])
def test_engine_marker_policy(engine, text, expected):
    from app.core.tts.emotions import apply_emotion

    assert apply_emotion(engine, text)[0] == expected


def test_piper_command_uses_flags(tmp_path, monkeypatch):
    from app.core.tts.engines.piper import PiperEngine

    model = tmp_path / "v.onnx"
    model.write_bytes(b"fake")
    captured = {}

    class Done:
        returncode = 0
        stderr = b""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["stdin"] = kwargs.get("input")
        out = cmd[cmd.index("--output_file") + 1]
        with open(out, "wb") as fh:
            fh.write(b"WAV")
        return Done()

    monkeypatch.setattr("app.core.tts.engines.piper.subprocess.run", fake_run)
    monkeypatch.setattr(PiperEngine, "is_available", lambda self: True)
    eng = PiperEngine(model_path=str(model))
    assert eng.synthesize("[sad] Blue rain.") == b"WAV"
    assert "--length-scale" in captured["cmd"]
    assert captured["stdin"] == "Blue rain.".encode()


def test_generator_emotion_passthrough(tmp_path, monkeypatch):
    from app.core.tts import generator as gen

    seen = {}

    class FakeEng:
        def synthesize(self, text, voice="", emotion="neutral"):
            seen.update(text=text, emotion=emotion)
            return b"AUDIO"

    monkeypatch.setattr(gen, "get_engine", lambda name, voice="": FakeEng())
    for engine in ("xtts", "silero"):
        audio = gen.generate_voice("[laughs] hi [score]", voice="v", engine=engine, emotion="happy")
        assert audio == b"AUDIO"
        assert seen == {"text": "hi [score]", "emotion": "happy"}
