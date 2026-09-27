"""DeepSeek provider (OpenAI-compatible)."""

from .openai_provider import OpenAICompatibleProvider

__all__ = ["DeepSeekProvider"]


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek adapter."""

    name = "deepseek"
    env_key = "DEEPSEEK_API_KEY"
    default_model = "deepseek-chat"
    api_url = "https://api.deepseek.com/chat/completions"
