"""Calendar-specific settings model."""

from datetime import datetime

from pydantic import BaseModel


class CalendarSettings(BaseModel):
    """Calendar-specific configuration.
    
    Stored in config.json within each calendar directory.
    These settings control calendar-specific defaults and preferences.
    
    The calendar id is inferred from the directory name and not stored here.
    The optional name field is a human-friendly display name.
    """

    name: str | None = None  # Display name (falls back to id if not set)
    template: str | None = None
    description: str | None = None
    created: datetime

    class Config:
        """Pydantic config."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
