"""Translation via the AI provider router (no new deps).

Uses any configured text provider (Ollama works fully offline).
Game dialogue is translated line by line to keep speaker timing;
tags like [happy] are preserved by translating only the clean text.
"""

from dataclasses import replace

from app.core.extractor.models import ExtractedLine
from app.core.tts.emotions import parse_emotion
from app.models.dialogue import Dialogue
from app.models.line import Line

__all__ = ["translate_text", "translate_line", "translate_lines", "SUPPORTED_HINT"]


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


def translate_line(line: Line, target: str, source: str = "auto",
                   provider: str = "ollama", api_key: str = "", model: str = "") -> Line:
    if line.manual_override and line.target_lang == target and line.translated_text:
        return line
    source_lang = line.source_lang if source == "auto" else source
    emotion, clean = parse_emotion(line.source_text)
    translated = translate_text(clean, target, source_lang, provider, api_key, model)
    if not translated.strip():
        raise ValueError("Translation is empty")
    tag = "" if emotion == "neutral" else f"[{emotion}] "
    return replace(
        line, source_lang=source_lang, target_lang=target,
        translated_text=tag + translated, tts_text=translated,
        emotion=line.emotion if emotion == "neutral" else emotion,
        metadata={**line.metadata, "translated_to": target},
    )


def translate_lines(lines: list[Line | Dialogue | ExtractedLine], target: str, source: str = "auto",
                    provider: str = "ollama", api_key: str = "", model: str = "") -> list[Line]:
    """Accept earlier extractor/CLI models at the boundary; always return Lines."""
    result = []
    for line in lines:
        if not isinstance(line, Line):
            line = Line(
                engine_id=getattr(line, "engine", ""), source_file=line.source_file,
                line_no=line.line_no, speaker=line.speaker, source_text=line.text,
                metadata=line.metadata,
            )
        result.append(translate_line(line, target, source, provider, api_key, model))
    return result


SUPPORTED_HINT = "Any target language the provider supports (e.g. en, ru, ja, de, fr)."
