"""Event model with Pydantic v2 validation."""

from datetime import date, time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, computed_field, field_validator, model_validator


class EventType(str, Enum):
    """Event type enumeration."""

    ON_CALL = "ON_CALL"
    ENDOSCOPY = "ENDOSCOPY"
    CCSC = "CCSC"
    CLINIC = "CLINIC"
    ADMIN = "ADMIN"
    OTHER = "OTHER"


class EventTypeDetector:
    """Detects event type from title string."""

    @staticmethod
    def detect_type(title: str) -> EventType:
        """Detect event type from title."""
        title_lower = title.lower()

        # On Call events (both "Primary on call" and "Endo on call")
        if "on call" in title_lower:
            return EventType.ON_CALL

        # Endoscopy events
        if "endoscopy" in title_lower or "endo" in title_lower:
            return EventType.ENDOSCOPY

        # CCSC events
        if "ccsc" in title_lower:
            return EventType.CCSC

        # Clinic events
        if "clinic" in title_lower:
            return EventType.CLINIC

        # Admin events
        if "admin" in title_lower:
            return EventType.ADMIN

        # Default to OTHER
        return EventType.OTHER


class Event(BaseModel):
    """Event model with validation and computed fields."""

    title: str
    date: date
    start: Optional[time] = None
    end: Optional[time] = None
    end_date: Optional[date] = None
    location: Optional[str] = None

    @field_validator("start", "end", mode="before")
    @classmethod
    def convert_time_string(cls, v):
        """Convert HHMM string to time object."""
        if v is None:
            return None
        if isinstance(v, time):
            return v
        if isinstance(v, str):
            # Handle HHMM format (e.g., "1230" -> 12:30)
            if len(v) == 4 and v.isdigit():
                hour = int(v[:2])
                minute = int(v[2:])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return time(hour, minute)
        raise ValueError(f"Invalid time format: {v}")

    @model_validator(mode="after")
    def validate_dates(self):
        """Validate date consistency and overnight event detection."""
        if self.end_date is not None:
            if self.end_date < self.date:
                raise ValueError("end_date must be >= date")
        return self

    @computed_field
    @property
    def type(self) -> EventType:
        """Automatically detect event type from title."""
        return EventTypeDetector.detect_type(self.title)

    @computed_field
    @property
    def is_all_day(self) -> bool:
        """True if start and end are None."""
        return self.start is None and self.end is None

    @computed_field
    @property
    def is_overnight(self) -> bool:
        """True if end_date is set and end_date > date."""
        return self.end_date is not None and self.end_date > self.date

    @computed_field
    @property
    def requires_location(self) -> bool:
        """True based on event type (e.g., Clinic, Endoscopy)."""
        return self.type in (EventType.CLINIC, EventType.ENDOSCOPY)

    class Config:
        """Pydantic config."""

        json_encoders = {
            date: lambda v: v.isoformat(),
            time: lambda v: v.strftime("%H%M"),
        }
