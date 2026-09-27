"""Provider tests (offline: requests.post is mocked)."""

from unittest.mock import MagicMock, patch

import pytest


def _resp(payload, status=200):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload
    m.text = str(payload)[:300]
    return m


def test_router():
    from app.providers.router import get_provider, list_providers

    assert list_providers() == ["anthropic", "deepseek", "groq", "mistral", "ollama", "openai"]
    assert get_provider("openai", api_key="k").name == "openai"
    assert get_provider("OLLAMA").name == "ollama"
    with pytest.raises(ValueError):
        get_provider("nope")


def test_openai_complete():
    from app.providers.openai_provider import OpenAIProvider

    with patch("requests.post", return_value=_resp({"choices": [{"message": {"content": "hi"}}]})) as p:
        text = OpenAIProvider(api_key="k").complete("hello")
    assert text == "hi"
    _, kwargs = p.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer k"


def test_anthropic_complete():
    from app.providers.anthropic_provider import AnthropicProvider

    payload = {"content": [{"type": "text", "text": "bonjour"}]}
    with patch("requests.post", return_value=_resp(payload)):
        assert AnthropicProvider(api_key="k").complete("hello") == "bonjour"


def test_ollama_no_key():
    from app.providers.ollama_provider import OllamaProvider

    payload = {"message": {"content": "local hi"}}
    with patch("requests.post", return_value=_resp(payload)) as p:
        assert OllamaProvider().complete("hello") == "local hi"
    assert "localhost" in p.call_args[0][0]


def test_missing_key_and_http_error():
    from app.providers.groq_provider import GroqProvider

    with pytest.raises(RuntimeError):
        GroqProvider(api_key="").complete("hi")  # no key, no network call
    with patch("requests.post", return_value=_resp({}, status=401)):
        with pytest.raises(RuntimeError):
            GroqProvider(api_key="k").complete("hi")
