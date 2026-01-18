"""Tests for output layer."""

import tempfile
from datetime import date, datetime, time
from pathlib import Path

import pytest
from icalendar import Calendar as ICalendar

from app.models.calendar import Calendar
from app.models.event import Event
from app.output.ics_writer import ICSWriter


def make_calendar(events: list[Event], name: str = "test") -> Calendar:
    """Helper to create a Calendar with default metadata."""
    now = datetime.now()
    return Calendar(
        events=events,
        name=name,
        created=now,
        last_updated=now,
    )


def test_ics_writer():
    """Test ICSWriter creates valid ICS file."""
    events = [
        Event(
            title="Test Event",
            date=date(2025, 1, 1),
            start=time(9, 0),
            end=time(10, 0),
        )
    ]
    calendar = make_calendar(events)

    with tempfile.NamedTemporaryFile(suffix=".ics", delete=False) as f:
        temp_path = Path(f.name)

    try:
        writer = ICSWriter()
        writer.write_calendar(calendar, temp_path)

        # Verify file was created
        assert temp_path.exists()

        # Verify it's valid ICS
        with open(temp_path, "rb") as f:
            ical_content = f.read()
            cal = ICalendar.from_ical(ical_content)
            assert cal is not None

        # Verify content
        assert b"BEGIN:VCALENDAR" in ical_content
        assert b"BEGIN:VEVENT" in ical_content
        assert b"SUMMARY:Test Event" in ical_content
    finally:
        temp_path.unlink()


def test_ics_writer_all_day_event():
    """Test ICSWriter handles all-day events."""
    events = [
        Event(
            title="All Day Event",
            date=date(2025, 1, 1),
        )
    ]
    calendar = make_calendar(events)

    with tempfile.NamedTemporaryFile(suffix=".ics", delete=False) as f:
        temp_path = Path(f.name)

    try:
        writer = ICSWriter()
        writer.write_calendar(calendar, temp_path)

        with open(temp_path, "rb") as f:
            ical_content = f.read()

        # All-day events should use DATE format
        assert (
            b"DTSTART;VALUE=DATE:20250101" in ical_content
            or b"DTSTART:20250101" in ical_content
        )
    finally:
        temp_path.unlink()


def test_ics_writer_get_extension():
    """Test ICSWriter returns correct extension."""
    writer = ICSWriter()
    assert writer.get_extension() == "ics"


def test_calendar_save_load():
    """Test Calendar native JSON save/load."""
    events = [
        Event(
            title="Test Event",
            date=date(2025, 1, 1),
            start=time(9, 0),
            end=time(10, 0),
        )
    ]
    calendar = make_calendar(events, name="test_calendar")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = Path(f.name)

    try:
        # Save using native method
        calendar.save(temp_path)

        # Verify file was created
        assert temp_path.exists()

        # Load back using native method
        loaded = Calendar.load(temp_path)

        # Verify data integrity
        assert loaded.name == calendar.name
        assert len(loaded.events) == 1
        assert loaded.events[0].title == "Test Event"
    finally:
        temp_path.unlink()
