"""Translation via the AI provider router (no new deps).

Uses any configured text provider (Ollama works fully offline).
Game dialogue is translated line by line to keep speaker timing;
tags like [happy] are preserved by translating only the clean text.
"""

from dataclasses import replace

__all__ = ["translate_text", "translate_lines", "SUPPORTED_HINT"]


def translate_text(text: str, target: str = "en", source: str = "auto",
                   provider: str = "ollama", api_key: str = "", model: str = "") -> str:
    """Translate one string. Returns stripped translation."""
    if not text or not text.strip():
        return text
    from app.providers.router import get_provider

    llm = get_provider(provider, api_key=api_key, model=model)
    out = llm.complete(
        f"Translate the following game dialogue line from {source} to {target}. "
        f"Reply with ONLY the translation, no quotes or explanations:\n{text}",
        system="You are a game localizer. Translate concisely, keep names untranslated.",
    )
    return out.strip().strip("\"'")


def translate_lines(lines: list, target: str, source: str = "auto",
                    provider: str = "ollama", api_key: str = "", model: str = "") -> list:
    """Translate dialogue texts, preserving speakers and metadata."""
    from app.studio.core.tts.emotions import parse_emotion

    out: list = []
    for ln in lines:
        emotion, clean = parse_emotion(ln.text)
        tag = "" if emotion == "neutral" else f"[{emotion}] "
        trans = translate_text(clean, target, source, provider, api_key, model)
        out.append(replace(ln, text=tag + trans,
                           metadata={**ln.metadata, "original_text": ln.text,
                                     "translated_to": target}))
    return out


SUPPORTED_HINT = "Any target language the provider supports (e.g. en, ru, ja, de, fr)."
