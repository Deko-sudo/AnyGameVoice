"""Character model."""

from dataclasses import dataclass


@dataclass
class Character:
    """Game character."""

    name: str = ""
