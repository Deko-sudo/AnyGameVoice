"""File utils."""

def ensure_dir(path: str) -> None:
    """Ensure dir exists (stub)."""
    import os

    os.makedirs(path, exist_ok=True)
