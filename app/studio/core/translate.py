"""Translation via the AI provider router (no new deps).

Uses any configured text provider (Ollama works fully offline).
Game dialogue is translated line by line to keep speaker timing;
tags like [happy] are preserved by translating only the clean text.
"""

from dataclasses import replace

from app.core.translate import translate_text

__all__ = ["translate_text", "translate_lines", "SUPPORTED_HINT"]


def translate_lines(lines: list, target: str, source: str = "auto",
                    provider: str = "ollama", api_key: str = "", model: str = "", base_url: str = "", api_format: str = "openai_chat") -> list:
    """Translate dialogue texts, preserving speakers and metadata."""
    from app.studio.core.tts.emotions import parse_emotion

    out: list = []
    for ln in lines:
        emotion, clean = parse_emotion(ln.text)
        tag = "" if emotion == "neutral" else f"[{emotion}] "
        trans = translate_text(clean, target, source, provider, api_key, model, base_url, api_format)
        out.append(replace(ln, text=tag + trans,
                           metadata={**ln.metadata, "original_text": ln.text,
                                     "translated_to": target}))
    return out


SUPPORTED_HINT = "Any target language the provider supports (e.g. en, ru, ja, de, fr)."
