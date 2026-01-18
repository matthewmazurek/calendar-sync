"""Tests for Pydantic models."""

from datetime import date, datetime, time

import pytest

from app.models.calendar import Calendar
from app.models.event import Event
from app.processing.merge_strategies import infer_year


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


def test_event_uid():
    """Test event uid field."""
    event = Event(
        title="Test Event",
        date=date(2025, 1, 1),
        uid="test-uid-123",
    )
    assert event.uid == "test-uid-123"
    
    # uid is optional
    event2 = Event(title="No UID", date=date(2025, 1, 1))
    assert event2.uid is None


def test_infer_year_single_year():
    """Test year inference with single year events."""
    events = [
        Event(title="Event 1", date=date(2025, 1, 1)),
        Event(title="Event 2", date=date(2025, 2, 1)),
    ]
    assert infer_year(events) == 2025


def test_infer_year_multi_year():
    """Test year inference with multi-year events."""
    events = [
        Event(title="Event 1", date=date(2025, 1, 1)),
        Event(title="Event 2", date=date(2026, 1, 1)),
    ]
    assert infer_year(events) is None


def test_infer_year_empty():
    """Test year inference with no events."""
    assert infer_year([]) is None


def test_calendar_creation():
    """Test unified calendar creation."""
    now = datetime.now()
    events = [Event(title="Event 1", date=date(2025, 1, 1))]
    
    calendar = Calendar(
        events=events,
        name="test_calendar",
        created=now,
        last_updated=now,
    )
    
    assert calendar.name == "test_calendar"
    assert len(calendar.events) == 1
    assert calendar.created == now
    assert calendar.last_updated == now


def test_calendar_metadata_fields():
    """Test calendar metadata fields."""
    now = datetime.now()
    events = [Event(title="Event 1", date=date(2025, 1, 1))]
    
    calendar = Calendar(
        events=events,
        name="test_calendar",
        created=now,
        last_updated=now,
        source="test_source",
        source_revised_at=date(2025, 1, 15),
        template_name="default",
        template_version="1.0",
    )
    
    assert calendar.source == "test_source"
    assert calendar.source_revised_at == date(2025, 1, 15)
    assert calendar.template_name == "default"
    assert calendar.template_version == "1.0"
