"""Voice model."""

from dataclasses import dataclass


@dataclass
class Voice:
    """Voice preset (local sample or engine voice)."""

    name: str = ""
    path: str = ""
    engine: str = ""
    sample_rate: int = 22050
