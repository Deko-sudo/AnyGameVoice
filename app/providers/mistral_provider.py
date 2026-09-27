"""Mistral provider (OpenAI-compatible)."""

from .openai_provider import OpenAICompatibleProvider

__all__ = ["MistralProvider"]


class MistralProvider(OpenAICompatibleProvider):
    """Mistral AI adapter."""

    name = "mistral"
    env_key = "MISTRAL_API_KEY"
    default_model = "mistral-small-latest"
    api_url = "https://api.mistral.ai/v1/chat/completions"
