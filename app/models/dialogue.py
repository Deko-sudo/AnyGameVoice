"""Dialogue model."""

from dataclasses import dataclass, field


@dataclass
class Dialogue:
    """Single dialogue line extracted from a game."""

    speaker: str = ""
    text: str = ""
    source_file: str = ""
    line_no: int = 0
    engine: str = ""
    metadata: dict = field(default_factory=dict)
