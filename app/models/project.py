"""Project model."""

from dataclasses import dataclass, field


@dataclass
class Project:
    """Voice modding project."""

    name: str = ""
    game_path: str = ""
    engine: str = ""
    characters: list = field(default_factory=list)
    settings: dict = field(default_factory=dict)
