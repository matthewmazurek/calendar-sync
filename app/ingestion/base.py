"""Base classes for calendar readers."""

from pathlib import Path
from typing import Dict, List, Protocol

from app.exceptions import UnsupportedFormatError
from app.models.calendar import Calendar


class CalendarReader(Protocol):
    """Protocol for calendar readers."""

    def read(self, path: Path) -> Calendar:
        """Read calendar from file path."""
        ...


class ReaderRegistry:
    """Registry for calendar readers by file extension."""

    def __init__(self):
        """Initialize registry."""
        self._readers: Dict[str, CalendarReader] = {}

    def register(self, reader: CalendarReader, extensions: List[str]) -> None:
        """Register reader for file extensions."""
        for ext in extensions:
            # Normalize extension (remove leading dot, lowercase)
            normalized_ext = ext.lstrip(".").lower()
            self._readers[normalized_ext] = reader

    def get_reader(self, path: Path) -> CalendarReader:
        """Get reader by file extension."""
        ext = path.suffix.lstrip(".").lower()
        if ext not in self._readers:
            raise UnsupportedFormatError(
                f"Unsupported file format: .{ext}. Supported formats: {', '.join(sorted(set(ext.lstrip('.') for ext in self._readers.keys())))}"
            )
        return self._readers[ext]
