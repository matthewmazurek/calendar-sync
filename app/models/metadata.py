"""Calendar metadata model with Pydantic v2."""

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel

from app.models.calendar import Calendar


class CalendarMetadata(BaseModel):
    """Calendar metadata model."""

    name: str
    source: str | None = None
    created: datetime
    last_updated: datetime
    composed_from: list[str] | None = None
    source_revised_at: date | None = None
    template_name: str | None = None
    template_version: str | None = None

    class Config:
        """Pydantic config."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class CalendarWithMetadata(BaseModel):
    """Wrapper for Calendar with metadata."""

    calendar: Calendar
    metadata: CalendarMetadata

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "calendar": self.calendar.model_dump(),
            "metadata": self.metadata.model_dump(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CalendarWithMetadata":
        """Create from dictionary."""
        return cls(
            calendar=Calendar(**data["calendar"]),
            metadata=CalendarMetadata(**data["metadata"]),
        )

    def save(self, path: Path) -> None:
        """Save to native JSON format (canonical storage).
        
        Uses compact serialization:
        - Excludes None values
        - Excludes computed fields (is_all_day, is_overnight)
        """
        import json
        from datetime import date, time, datetime
        
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
            exclude={
                "calendar": {
                    "events": {
                        "__all__": {"is_all_day", "is_overnight"}
                    }
                }
            }
        )
        path.write_text(json.dumps(data, indent=2, default=json_encoder))

    @classmethod
    def load(cls, path: Path) -> "CalendarWithMetadata":
        """Load from native JSON format."""
        return cls.model_validate_json(path.read_text())
