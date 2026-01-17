"""Tests for Pydantic models."""

from datetime import date, time

import pytest

from app.exceptions import InvalidYearError, ValidationError
from app.models.calendar import Calendar
from app.models.event import Event
from app.models.metadata import CalendarMetadata, CalendarWithMetadata


def test_event_creation():
    """Test basic event creation."""
    event = Event(
        title="Test Event",
        date=date(2025, 1, 1),
        start=time(9, 0),
        end=time(10, 0),
    )
    assert event.title == "Test Event"
    assert event.date == date(2025, 1, 1)
    assert event.start == time(9, 0)
    assert event.end == time(10, 0)


def test_event_time_string_conversion():
    """Test time string conversion."""
    event = Event(
        title="Test Event",
        date=date(2025, 1, 1),
        start="0900",
        end="1700",
    )
    assert event.start == time(9, 0)
    assert event.end == time(17, 0)


def test_event_computed_fields():
    """Test computed fields."""
    # All-day event
    event1 = Event(title="All Day Event", date=date(2025, 1, 1))
    assert event1.is_all_day is True

    # Timed event
    event2 = Event(
        title="Timed Event",
        date=date(2025, 1, 1),
        start=time(9, 0),
        end=time(10, 0),
    )
    assert event2.is_all_day is False

    # Overnight event
    event3 = Event(
        title="Overnight Event",
        date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
    )
    assert event3.is_overnight is True


def test_calendar_year_validation():
    """Test calendar year validation."""
    # Single year calendar
    events = [
        Event(title="Event 1", date=date(2025, 1, 1)),
        Event(title="Event 2", date=date(2025, 2, 1)),
    ]
    calendar = Calendar(events=events, year=2025)
    assert calendar.year == 2025

    # Multi-year calendar should fail validation
    events_multi = [
        Event(title="Event 1", date=date(2025, 1, 1)),
        Event(title="Event 2", date=date(2026, 1, 1)),
    ]
    with pytest.raises(ValueError):
        Calendar(events=events_multi, year=2025)


def test_calendar_metadata():
    """Test calendar metadata."""
    from datetime import datetime

    metadata = CalendarMetadata(
        name="test_calendar",
        created=datetime.now(),
        last_updated=datetime.now(),
    )
    assert metadata.name == "test_calendar"


def test_calendar_with_metadata():
    """Test calendar with metadata wrapper."""
    from datetime import datetime

    events = [Event(title="Event 1", date=date(2025, 1, 1))]
    calendar = Calendar(events=events)
    metadata = CalendarMetadata(
        name="test",
        created=datetime.now(),
        last_updated=datetime.now(),
    )
    wrapper = CalendarWithMetadata(calendar=calendar, metadata=metadata)
    assert wrapper.calendar == calendar
    assert wrapper.metadata == metadata
