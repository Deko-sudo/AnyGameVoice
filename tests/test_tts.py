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
