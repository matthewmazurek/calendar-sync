"""Calendar model with Pydantic v2 validation."""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, model_validator

from app.models.event import Event


class Calendar(BaseModel):
    """Calendar model (pure domain model, no metadata)."""

    events: List[Event]
    revised_date: Optional[date] = None
    year: Optional[int] = None

    @model_validator(mode="after")
    def validate_year(self):
        """Ensure all events are from same year (if year specified and events exist)."""
        if not self.events:
            return self

        # Infer year from events if not specified
        if self.year is None:
            years = {event.date.year for event in self.events}
            if len(years) == 1:
                self.year = years.pop()
            elif len(years) > 1:
                # Multi-year calendar, leave year as None
                pass
        else:
            # Validate all events are from the specified year
            for event in self.events:
                if event.date.year != self.year:
                    raise ValueError(
                        f"Event {event.title} on {event.date} is from year {event.date.year}, "
                        f"but calendar year is {self.year}"
                    )

        return self
