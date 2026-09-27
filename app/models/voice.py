"""Voice model."""

from dataclasses import dataclass


@dataclass
class Voice:
    """Voice preset."""

    name: str = ""
    path: str = ""
