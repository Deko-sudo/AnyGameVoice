"""Emotion tests (offline)."""


def test_parse_emotion():
    from app.core.tts.emotions import parse_emotion

    assert parse_emotion("[happy] Hello!") == ("happy", "Hello!")
    assert parse_emotion('<emotion="sad">Rain.') == ("sad", "Rain.")
    assert parse_emotion("Plain line.") == ("neutral", "Plain line.")
    emo, clean = parse_emotion("[dragon] Rawr")
    assert emo == "neutral" and clean == "Rawr"  # unknown tag dropped, never read aloud
    emo, clean = parse_emotion("[laughs] Ha ha")
    assert emo == "neutral" and "[laughs]" in clean  # bark-native marker kept


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
    assert gen.generate_voice("hi", voice="v", engine="xtts", emotion="happy") == b"AUDIO"
    assert seen == {"text": "hi", "emotion": "happy"}
