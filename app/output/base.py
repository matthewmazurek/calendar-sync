"""Base classes for calendar writers."""

from pathlib import Path
from typing import Protocol

from app.models.metadata import CalendarWithMetadata


class CalendarWriter(Protocol):
    """Protocol for calendar writers."""

    def write(self, calendar: CalendarWithMetadata, path: Path) -> None:
        """Write calendar to file path."""
        ...

    def get_extension(self) -> str:
        """Returns file extension (e.g., 'ics', 'json')."""
        ...
