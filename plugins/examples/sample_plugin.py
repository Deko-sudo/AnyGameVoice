"""Sample plugin example."""


class SamplePlugin:
    """Example engine plugin."""

    name = "sample"

    def detect(self, game_path: str) -> bool:
        """Return True if this plugin handles the game."""
        return False

    def extract(self, game_path: str) -> list:
        """Extract dialogue lines."""
        return []
