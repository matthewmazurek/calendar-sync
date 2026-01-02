"""Tests for output layer."""

from datetime import date, datetime, time
from pathlib import Path
import tempfile

import pytest
from icalendar import Calendar as ICalendar

from app.models.calendar import Calendar
from app.models.event import Event
from app.models.metadata import CalendarMetadata, CalendarWithMetadata
from app.output.ics_writer import ICSWriter
from app.output.json_writer import JSONWriter


def make_calendar_with_metadata(calendar: Calendar, name: str = "test") -> CalendarWithMetadata:
    """Helper to wrap a Calendar with default metadata."""
    metadata = CalendarMetadata(
        name=name,
        created=datetime.now(),
        last_updated=datetime.now(),
    )
    return CalendarWithMetadata(calendar=calendar, metadata=metadata)


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
    calendar = Calendar(events=events)
    calendar_with_metadata = make_calendar_with_metadata(calendar)

    with tempfile.NamedTemporaryFile(suffix='.ics', delete=False) as f:
        temp_path = Path(f.name)

    try:
        writer = ICSWriter()
        writer.write(calendar_with_metadata, temp_path)

        # Verify file was created
        assert temp_path.exists()

        # Verify it's valid ICS
        with open(temp_path, 'rb') as f:
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
    calendar = Calendar(events=events)
    calendar_with_metadata = make_calendar_with_metadata(calendar)

    with tempfile.NamedTemporaryFile(suffix='.ics', delete=False) as f:
        temp_path = Path(f.name)

    try:
        writer = ICSWriter()
        writer.write(calendar_with_metadata, temp_path)

        with open(temp_path, 'rb') as f:
            ical_content = f.read()

        # All-day events should use DATE format
        assert b"DTSTART;VALUE=DATE:20250101" in ical_content or b"DTSTART:20250101" in ical_content
    finally:
        temp_path.unlink()


def test_ics_writer_get_extension():
    """Test ICSWriter returns correct extension."""
    writer = ICSWriter()
    assert writer.get_extension() == "ics"


def test_json_writer():
    """Test JSONWriter creates valid JSON file."""
    events = [
        Event(
            title="Test Event",
            date=date(2025, 1, 1),
            start=time(9, 0),
            end=time(10, 0),
        )
    ]
    calendar = Calendar(events=events)
    calendar_with_metadata = make_calendar_with_metadata(calendar)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = Path(f.name)

    try:
        writer = JSONWriter()
        writer.write(calendar_with_metadata, temp_path)

        # Verify file was created
        assert temp_path.exists()

        # Verify it's valid JSON
        import json
        with open(temp_path, 'r') as f:
            data = json.load(f)
            assert "events" in data
            assert len(data["events"]) == 1
            assert data["events"][0]["title"] == "Test Event"
    finally:
        temp_path.unlink()


def test_json_writer_get_extension():
    """Test JSONWriter returns correct extension."""
    writer = JSONWriter()
    assert writer.get_extension() == "json"
