"""Project model."""

from dataclasses import dataclass


@dataclass
class Project:
    """Voice modding project."""

    name: str = ""
    game_path: str = ""
