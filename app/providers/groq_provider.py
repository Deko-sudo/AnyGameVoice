"""Groq provider (OpenAI-compatible)."""

from .openai_provider import OpenAICompatibleProvider

__all__ = ["GroqProvider"]


class GroqProvider(OpenAICompatibleProvider):
    """Groq adapter (fast LPU inference)."""

    name = "groq"
    env_key = "GROQ_API_KEY"
    default_model = "llama-3.3-70b-versatile"
    api_url = "https://api.groq.com/openai/v1/chat/completions"
