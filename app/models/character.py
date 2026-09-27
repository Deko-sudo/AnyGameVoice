"""Character model."""

from dataclasses import dataclass, field


@dataclass
class Character:
    """Game character with an assigned voice."""

    name: str = ""
    voice: str = ""
    line_count: int = 0
    aliases: list = field(default_factory=list)
