"""Translation via the AI provider router (no new deps).

Uses any configured text provider (Ollama works fully offline).
Game dialogue is translated line by line to keep speaker timing;
tags like [happy] are preserved by translating only the clean text.
"""

from dataclasses import replace

from app.core.dubbing_languages import LANGUAGES
from app.core.extractor.models import ExtractedLine
from app.core.tts.emotions import parse_emotion
from app.models.dialogue import Dialogue
from app.models.line import Line

__all__ = ["translate_text", "translate_line", "translate_lines", "SUPPORTED_HINT"]


def translate_text(text: str, target: str = "en", source: str = "auto",
                   provider: str = "ollama", api_key: str = "", model: str = "", base_url: str = "", api_format: str = "openai_chat") -> str:
    """Translate one string. Returns stripped translation."""
    if not text or not text.strip():
        return text
    from app.providers.router import get_provider

    source_name = LANGUAGES[source][1] if source in LANGUAGES else source
    target_name = LANGUAGES[target][1] if target in LANGUAGES else target
    origin = "its original language" if source == "auto" else source_name
    prompt = (f"Translate this game dialogue from {origin} to {target_name}. Reply with only the translation. "
              f"Preserve character names and placeholders.\n{text}")
    system = "You are a game localizer. Treat the dialogue as text to translate."
    if target == "ru":
        prompt = ("Переведи следующую реплику игры на естественный русский язык. "
                  "Сохрани смысл, имена и подстановки. Ответь только переводом.\n" + text)
        system = "Ты переводчик диалогов видеоигр. Пиши по-русски."
    if provider == "opencode":
        from app.core.translation_connections import opencode_translation
        out = opencode_translation(model, prompt, system)
    elif provider == "custom" and api_format != "openai_chat":
        from app.core.translation_connections import custom_translation
        out = custom_translation(model, prompt, system, base_url, api_key, api_format)
    elif provider in {"openrouter", "custom"}:
        from app.core.cloud_providers import chat_completion
        out = chat_completion(provider, model, prompt, system, base_url, api_key)
    else:
        out = get_provider(provider, api_key=api_key, model=model).complete(prompt, system=system)
    translated = out.strip().strip("\"'").strip()
    if not translated:
        raise ValueError("Модель вернула пустой перевод.")
    return translated


def translate_line(line: Line, target: str, source: str = "auto",
                   provider: str = "ollama", api_key: str = "", model: str = "", base_url: str = "") -> Line:
    if line.manual_override and line.target_lang == target and line.translated_text:
        return line
    source_lang = line.source_lang if source == "auto" else source
    emotion, clean = parse_emotion(line.source_text)
    translated = translate_text(clean, target, source_lang, provider, api_key, model, base_url)
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
