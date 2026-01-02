"""Tests for ICS output writer."""

from datetime import date, datetime, time

import pytest
from icalendar import Calendar as ICalendar

from app.models.calendar import Calendar
from app.models.event import Event
from app.models.metadata import CalendarMetadata, CalendarWithMetadata
from app.output.ics_writer import ICSWriter

WORK_LOCATION = "1403 29 St NW, Calgary AB T2N 2T9, Canada"


def make_calendar_with_metadata(calendar: Calendar, name: str = "test") -> CalendarWithMetadata:
    """Helper to wrap a Calendar with default metadata."""
    metadata = CalendarMetadata(
        name=name,
        created=datetime.now(),
        last_updated=datetime.now(),
    )
    return CalendarWithMetadata(calendar=calendar, metadata=metadata)


def test_make_calendar_creates_valid_icalendar():
    """Test that ICSWriter creates a valid iCalendar file."""
    import tempfile
    from pathlib import Path

    events = [
        Event(
            title="Test Event",
            date=date(2025, 1, 1),
            start=time(9, 0),
            end=time(10, 0),
        )
    ]
    calendar = Calendar(events=events)

    with tempfile.NamedTemporaryFile(suffix='.ics', delete=False) as f:
        temp_path = Path(f.name)

    try:
        writer = ICSWriter()
        calendar_with_metadata = make_calendar_with_metadata(calendar)
        writer.write(calendar_with_metadata, temp_path)

        with open(temp_path, 'rb') as f:
            ical_content = f.read()

        assert b"BEGIN:VCALENDAR" in ical_content
        assert b"END:VCALENDAR" in ical_content
        assert b"BEGIN:VEVENT" in ical_content
        assert b"END:VEVENT" in ical_content

        # Verify it's parseable
        cal = ICalendar.from_ical(ical_content)
        assert isinstance(cal, ICalendar)
    finally:
        temp_path.unlink()


def test_make_calendar_includes_all_required_fields():
    """Test that each VEVENT contains all required iCalendar fields."""
    import tempfile
    from pathlib import Path

    events = [
        Event(
            title="Test Event",
            date=date(2025, 1, 1),
            start=time(9, 0),
            end=time(10, 0),
        )
    ]
    calendar = Calendar(events=events)

    with tempfile.NamedTemporaryFile(suffix='.ics', delete=False) as f:
        temp_path = Path(f.name)

    try:
        writer = ICSWriter()
        calendar_with_metadata = make_calendar_with_metadata(calendar)
        writer.write(calendar_with_metadata, temp_path)

        with open(temp_path, 'rb') as f:
            ical_content = f.read()

        # Check for required fields
        assert b"SUMMARY:Test Event" in ical_content
        assert b"DTSTART:20250101T090000" in ical_content
        assert b"DTEND:20250101T100000" in ical_content
        assert b"UID:" in ical_content
        assert b"DTSTAMP:" in ical_content
    finally:
        temp_path.unlink()


def test_make_calendar_handles_all_day_events():
    """Test that all-day events are properly formatted."""
    import tempfile
    from pathlib import Path

    events = [Event(title="All Day Event", date=date(2025, 1, 1))]
    calendar = Calendar(events=events)

    with tempfile.NamedTemporaryFile(suffix='.ics', delete=False) as f:
        temp_path = Path(f.name)

    try:
        writer = ICSWriter()
        calendar_with_metadata = make_calendar_with_metadata(calendar)
        writer.write(calendar_with_metadata, temp_path)

        with open(temp_path, 'rb') as f:
            ical_content = f.read()

        # All-day events should use DATE format without time
        assert b"DTSTART;VALUE=DATE:20250101" in ical_content or b"DTSTART:20250101" in ical_content
        assert b"DTEND;VALUE=DATE:20250102" in ical_content or b"DTEND:20250102" in ical_content  # End date is next day
    finally:
        temp_path.unlink()


def test_make_calendar_handles_multiple_events():
    """Test that multiple events are properly included."""
    import tempfile
    from pathlib import Path

    events = [
        Event(title="Event 1", date=date(2025, 1, 1), start=time(9, 0), end=time(10, 0)),
        Event(title="Event 2", date=date(2025, 1, 2)),
    ]
    calendar = Calendar(events=events)

    with tempfile.NamedTemporaryFile(suffix='.ics', delete=False) as f:
        temp_path = Path(f.name)

    try:
        writer = ICSWriter()
        calendar_with_metadata = make_calendar_with_metadata(calendar)
        writer.write(calendar_with_metadata, temp_path)

        with open(temp_path, 'rb') as f:
            ical_content = f.read()

        # Check both events are present
        assert ical_content.count(b"BEGIN:VEVENT") == 2
        assert ical_content.count(b"END:VEVENT") == 2
        assert b"SUMMARY:Event 1" in ical_content
        assert b"SUMMARY:Event 2" in ical_content
    finally:
        temp_path.unlink()


def test_calendar_location_handling():
    """Test that location and geo information is correctly added to calendar events."""
    import tempfile
    from pathlib import Path

    events = [
        Event(
            title="Endo Clinic",
            date=date(2025, 1, 1),
            start=time(9, 0),
            end=time(17, 0),
            location=WORK_LOCATION,
            location_geo=(51.065389, -114.133306),
            location_apple_title="Foothills Medical Centre",
        ),
        Event(
            title="Regular Meeting",
            date=date(2025, 1, 2),
            start=time(10, 0),
            end=time(11, 0),
            location="Other Location",
        ),
    ]
    calendar = Calendar(events=events)

    with tempfile.NamedTemporaryFile(suffix='.ics', delete=False) as f:
        temp_path = Path(f.name)

    try:
        writer = ICSWriter()
        calendar_with_metadata = make_calendar_with_metadata(calendar)
        writer.write(calendar_with_metadata, temp_path)

        with open(temp_path, 'rb') as f:
            ical_content = f.read()

        cal = ICalendar.from_ical(ical_content)

        # Find the events in the calendar
        endo_event = None
        regular_event = None
        for component in cal.walk():
            if component.name == "VEVENT":
                if component["summary"] == "Endo Clinic":
                    endo_event = component
                elif component["summary"] == "Regular Meeting":
                    regular_event = component

        # Check that Endo Clinic has location and geo information
        assert endo_event is not None
        assert "location" in endo_event
        assert "Foothills Medical Centre" in str(endo_event["location"])
        assert "geo" in endo_event

        # Check that Regular Meeting has location but no geo information
        assert regular_event is not None
        assert "location" in regular_event
        assert str(regular_event["location"]) == "Other Location"
        assert "geo" not in regular_event
    finally:
        temp_path.unlink()
