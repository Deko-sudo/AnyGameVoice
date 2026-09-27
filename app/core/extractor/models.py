"""Extractor data models."""

from dataclasses import dataclass


@dataclass
class ExtractedLine:
    """Single extracted line."""

    speaker: str = ""
    text: str = ""
