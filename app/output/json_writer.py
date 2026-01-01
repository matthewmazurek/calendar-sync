"""JSON file writer for calendar files."""

import json
from pathlib import Path

from app.models.calendar import Calendar


class JSONWriter:
    """Writer for JSON calendar files."""

    def write(self, calendar: Calendar, path: Path) -> None:
        """Write calendar to JSON file."""
        # Use Pydantic's JSON serialization
        json_str = calendar.model_dump_json(indent=2)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_str)

    def get_extension(self) -> str:
        """Returns file extension."""
        return "json"
