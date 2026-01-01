"""Calendar metadata model with Pydantic v2."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.calendar import Calendar


class CalendarMetadata(BaseModel):
    """Calendar metadata model."""

    name: str
    source: Optional[str] = None
    created: datetime
    last_updated: datetime
    revision_count: int = 0
    composed_from: Optional[List[str]] = None
    format: str = "ics"  # "ics" or "json"
    source_revised_at: Optional[date] = None

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
