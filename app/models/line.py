"""A dialogue line throughout extraction, translation and speech generation."""

from dataclasses import dataclass, field


@dataclass
class Line:
    engine_id: str = ""
    source_file: str = ""
    line_no: int = 0
    speaker: str = ""
    source_text: str = ""
    source_lang: str = "auto"
    target_lang: str = ""
    translated_text: str = ""
    tts_text: str = ""
    voice_id: str = ""
    emotion: str = "neutral"
    duration_target: float | None = None
    manual_override: bool = False
    metadata: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Display text for the existing UI and subtitle writers."""
        return self.translated_text or self.source_text
