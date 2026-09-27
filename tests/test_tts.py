"""TTS tests."""


def test_voice_manager_stub():
    from app.core.tts.voice_manager import VoiceManager

    assert VoiceManager().list_voices() == []
