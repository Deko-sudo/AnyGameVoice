"""Queue priorities."""

from enum import IntEnum


class Priority(IntEnum):
    """Task priority."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
