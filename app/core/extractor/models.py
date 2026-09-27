"""Extractor data models."""

from dataclasses import dataclass, field


@dataclass
class ExtractedLine:
    """Single extracted line."""

    speaker: str = ""
    text: str = ""
    source_file: str = ""
    line_no: int = 0
    metadata: dict = field(default_factory=dict)


__all__ = ["ExtractedLine"]
