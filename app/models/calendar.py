"""Calendar model with Pydantic v2 validation."""

import json
from datetime import date, datetime, time
from pathlib import Path

from pydantic import BaseModel

from app.models.event import Event


class Calendar(BaseModel):
    """Calendar model with events and metadata.

    This is the unified calendar model that combines events with all metadata.
    Previously split across Calendar, CalendarMetadata, and CalendarWithMetadata.
    """

    # Events
    events: list[Event]

    # Metadata
    name: str
    created: datetime
    last_updated: datetime
    source: str | None = None
    source_revised_at: date | None = None
    composed_from: list[str] | None = None
    template_name: str | None = None
    template_version: str | None = None

    class Config:
        """Pydantic config."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            time: lambda v: v.strftime("%H%M"),
        }

    def save(self, path: Path) -> None:
        """Save to native JSON format (canonical storage).

        Uses compact serialization:
        - Excludes None values
        - Excludes computed fields (is_all_day, is_overnight)
        """

        def json_encoder(obj):
            """Custom JSON encoder for calendar types."""
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, date):
                return obj.isoformat()
            if isinstance(obj, time):
                return obj.strftime("%H%M")
            return str(obj)

        # Get dict with exclusions
        data = self.model_dump(
            exclude_none=True,
            exclude={"events": {"__all__": {"is_all_day", "is_overnight"}}},
        )
        path.write_text(json.dumps(data, indent=2, default=json_encoder))

    @classmethod
    def load(cls, path: Path) -> "Calendar":
        """Load from native JSON format.

        Supports both new flat format and legacy nested format for backward compatibility.
        Legacy format: {calendar: {events, ...}, metadata: {...}}
        New format: {events, name, created, ...}
        """
        data = json.loads(path.read_text())

        # Check if this is the legacy nested format
        if "calendar" in data and "metadata" in data:
            # Legacy format - flatten it
            calendar_data = data["calendar"]
            metadata = data["metadata"]

            flat_data = {
                "events": calendar_data.get("events", []),
                "name": metadata.get("name"),
                "created": metadata.get("created"),
                "last_updated": metadata.get("last_updated"),
                "source": metadata.get("source"),
                "source_revised_at": metadata.get("source_revised_at"),
                "composed_from": metadata.get("composed_from"),
                "template_name": metadata.get("template_name"),
                "template_version": metadata.get("template_version"),
            }
            return cls.model_validate(flat_data)

        # New flat format
        return cls.model_validate(data)
