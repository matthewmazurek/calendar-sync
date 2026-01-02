"""JSON file writer for calendar files."""

import json
from pathlib import Path

from app.models.metadata import CalendarWithMetadata


class JSONWriter:
    """Writer for JSON calendar files."""

    def write(self, calendar_with_metadata: CalendarWithMetadata, path: Path) -> None:
        """Write calendar to JSON file."""
        # Use Pydantic's JSON serialization (only calendar data, not metadata)
        json_str = calendar_with_metadata.calendar.model_dump_json(indent=2)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_str)

    def get_extension(self) -> str:
        """Returns file extension."""
        return "json"
