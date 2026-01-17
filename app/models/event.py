"""Event model with Pydantic v2 validation."""

from datetime import date, time

from pydantic import BaseModel, computed_field, field_validator, model_validator


class Event(BaseModel):
    """Event model with validation and computed fields."""

    title: str
    date: date
    start: time | None = None
    end: time | None = None
    end_date: date | None = None
    
    # Location: mutually exclusive - use location_id OR location, not both
    location: str | None = None           # Full address (override/legacy)
    location_id: str | None = None        # Reference to template location
    location_geo: tuple[float, float] | None = None
    location_apple_title: str | None = None
    
    type: str | None = None
    label: str | None = None
    busy: bool = True

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

    @model_validator(mode="after")
    def validate_location_exclusivity(self):
        """Ensure location and location_id are mutually exclusive."""
        if self.location and self.location_id:
            raise ValueError(
                "Cannot specify both 'location' and 'location_id'. "
                "Use 'location_id' to reference a template location, "
                "or 'location' for a custom address."
            )
        return self

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

    class Config:
        """Pydantic config."""

        json_encoders = {
            date: lambda v: v.isoformat(),
            time: lambda v: v.strftime("%H%M"),
        }
