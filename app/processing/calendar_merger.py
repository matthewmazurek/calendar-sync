"""Calendar merger for year-based replacement."""

from app.exceptions import InvalidYearError
from app.models.calendar import Calendar


def replace_year_in_calendar(
    new: Calendar, existing: Calendar, year: int
) -> Calendar:
    """
    Replace all events from specified year in existing calendar with events from new calendar.

    Args:
        new: New calendar with events to add
        existing: Existing calendar with events to merge
        year: Year to replace

    Returns:
        Merged Calendar object
    """
    # Validate new calendar contains events from single year matching year parameter
    if new.year is not None and new.year != year:
        raise InvalidYearError(
            f"New calendar year ({new.year}) does not match specified year ({year})"
        )

    # Check all events in new calendar are from specified year
    for event in new.events:
        if event.date.year != year:
            raise InvalidYearError(
                f"New calendar contains event from year {event.date.year}, "
                f"but specified year is {year}"
            )

    # Remove all events from existing calendar for the specified year
    filtered_events = [
        event for event in existing.events if event.date.year != year
    ]

    # Add all events from new calendar
    merged_events = filtered_events + new.events

    # Create merged calendar
    return Calendar(events=merged_events, revised_date=existing.revised_date)
