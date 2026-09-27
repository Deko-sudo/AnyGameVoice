"""TTS tests."""

import pytest


def test_voice_manager_stub(tmp_path):
    from app.core.tts.voice_manager import VoiceManager

    vm = VoiceManager(user_dir=tmp_path)
    assert vm.list_voices() == []


def test_voice_manager_add_remove(tmp_path):
    from app.core.tts.voice_manager import VoiceManager

    sample = tmp_path / "hero.wav"
    sample.write_bytes(b"RIFF....")
    user = tmp_path / "user"
    vm = VoiceManager(user_dir=user)
    v = vm.add_voice(str(sample))
    assert v.name == "hero"
    assert len(vm.list_voices()) == 1
    assert vm.remove_voice("hero") is True
    assert vm.list_voices() == []


def test_piper_missing_model():
    from app.core.tts.engines.piper import PiperEngine

    eng = PiperEngine(model_path="nonexistent.onnx")
    with pytest.raises((FileNotFoundError, RuntimeError)):
        eng.synthesize("hello", voice="nonexistent.onnx")


def test_generate_empty_text():
    from app.core.tts.generator import generate_voice

    with pytest.raises(ValueError):
        generate_voice("   ")


def test_engine_registry():
    from app.core.tts.generator import get_engine, list_engines

    engines = list_engines()
    assert set(engines) == {"piper", "xtts", "bark", "silero"}
    assert all(isinstance(v, bool) for v in engines.values())
    with pytest.raises(ValueError):
        get_engine("nonexistent")


def test_generate_needs_voice_model():
    from app.core.tts.generator import generate_voice

    with pytest.raises((FileNotFoundError, RuntimeError)):
        generate_voice("hello")  # default voice -> helpful error, no crash
