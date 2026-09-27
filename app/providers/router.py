"""Provider router (Phase 5)."""

from .anthropic_provider import AnthropicProvider
from .base import BaseProvider
from .deepseek_provider import DeepSeekProvider
from .groq_provider import GroqProvider
from .mistral_provider import MistralProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider

__all__ = ["get_provider", "list_providers"]

PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "groq": GroqProvider,
    "mistral": MistralProvider,
    "deepseek": DeepSeekProvider,
    "ollama": OllamaProvider,
}


def list_providers() -> list:
    """Return known provider names."""
    return sorted(PROVIDERS)


def get_provider(name: str, api_key: str = "", model: str = "") -> BaseProvider:
    """Build a provider by name. Raises ValueError for unknown names."""
    cls = PROVIDERS.get((name or "").lower())
    if cls is None:
        raise ValueError(f"Unknown provider: {name}. Known: {list_providers()}")
    return cls(api_key=api_key, model=model)
