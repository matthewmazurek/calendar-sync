"""Base classes for calendar writers."""

from pathlib import Path
from typing import Protocol

from app.models.calendar import Calendar


class CalendarWriter(Protocol):
    """Protocol for calendar writers."""

    def write(self, calendar: Calendar, path: Path) -> None:
        """Write calendar to file path."""
        ...

    def get_extension(self) -> str:
        """Returns file extension (e.g., 'ics', 'json')."""
        ...
