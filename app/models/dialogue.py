"""Dialogue model."""

from dataclasses import dataclass


@dataclass
class Dialogue:
    """Dialogue line."""

    speaker: str = ""
    text: str = ""
