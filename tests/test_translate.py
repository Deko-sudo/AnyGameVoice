"""Translation tests (provider mocked, offline)."""

from unittest.mock import MagicMock, patch


def _fake_provider(text="Hola"):
    m = MagicMock()
    m.complete.return_value = text
    return m


def test_translate_text():
    from app.core import translate as tr

    with patch("app.providers.router.get_provider", return_value=_fake_provider("  \"Hola\"  ")):
        assert tr.translate_text("Hello", target="es", provider="ollama") == "Hola"


def test_translate_preserves_emotion_and_speaker():
    from app.core.translate import translate_lines
    from app.models.dialogue import Dialogue

    lines = [Dialogue(speaker="e", text="[happy] Hello!", source_file="s.rpy", line_no=3)]
    with patch("app.providers.router.get_provider", return_value=_fake_provider("Hola!")):
        out = translate_lines(lines, "es")
    assert len(out) == 1
    assert out[0].speaker == "e"
    assert out[0].text == "[happy] Hola!"
    assert out[0].line_no == 3
    assert out[0].metadata["translated_to"] == "es"


def test_translate_empty():
    from app.core.translate import translate_text

    assert translate_text("   ", target="ru") == "   "
