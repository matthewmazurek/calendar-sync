from datetime import datetime

import pytest
from icalendar import Calendar

from app.calendar_generator import generate_ical
from app.event_processor import WORK_LOCATION


def test_make_calendar_creates_valid_icalendar():
    """Test that make_calendar returns a valid iCalendar object."""
    events = [
        {"title": "Test Event", "date": "2025-01-01", "start": "0900", "end": "1000"}
    ]

    calendar = generate_ical(events)
    assert isinstance(calendar, Calendar)

    # Convert to iCal format and check content
    ical_content = calendar.to_ical()
    assert b"BEGIN:VCALENDAR" in ical_content
    assert b"END:VCALENDAR" in ical_content
    assert b"BEGIN:VEVENT" in ical_content
    assert b"END:VEVENT" in ical_content


def test_make_calendar_includes_all_required_fields():
    """Test that each VEVENT contains all required iCalendar fields."""
    events = [
        {"title": "Test Event", "date": "2025-01-01", "start": "0900", "end": "1000"}
    ]

    calendar = generate_ical(events)
    ical_content = calendar.to_ical()

    # Check for required fields
    assert b"SUMMARY:Test Event" in ical_content
    assert b"DTSTART:20250101T090000" in ical_content
    assert b"DTEND:20250101T100000" in ical_content
    assert b"UID:" in ical_content
    assert b"DTSTAMP:" in ical_content


def test_make_calendar_handles_all_day_events():
    """Test that all-day events are properly formatted."""
    events = [{"title": "All Day Event", "date": "2025-01-01"}]

    calendar = generate_ical(events)
    ical_content = calendar.to_ical()

    # All-day events should use DATE format without time
    assert b"DTSTART;VALUE=DATE:20250101" in ical_content
    assert b"DTEND;VALUE=DATE:20250102" in ical_content  # End date is next day


def test_make_calendar_handles_multiple_events():
    """Test that multiple events are properly included."""
    events = [
        {"title": "Event 1", "date": "2025-01-01", "start": "0900", "end": "1000"},
        {"title": "Event 2", "date": "2025-01-02"},
    ]

    calendar = generate_ical(events)
    ical_content = calendar.to_ical()

    # Check both events are present
    assert ical_content.count(b"BEGIN:VEVENT") == 2
    assert ical_content.count(b"END:VEVENT") == 2
    assert b"SUMMARY:Event 1" in ical_content
    assert b"SUMMARY:Event 2" in ical_content


def test_calendar_location_handling():
    """Test that location and geo information is correctly added to calendar events."""
    events = [
        {
            "title": "Endo Clinic",
            "date": "2025-01-01",
            "start": "0900",
            "end": "1700",
            "location": WORK_LOCATION,
        },
        {
            "title": "Regular Meeting",
            "date": "2025-01-02",
            "start": "1000",
            "end": "1100",
            "location": "Other Location",
        },
    ]

    cal = generate_ical(events)

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
    assert "Foothills Medical Centre" in endo_event["location"]
    assert "1403 29 St NW, Calgary AB T2N 2T9, Canada" in endo_event["location"]
    assert "geo" in endo_event

    # Check that Regular Meeting has location but no geo information
    assert regular_event is not None
    assert "location" in regular_event
    assert regular_event["location"] == "Other Location"
    assert "geo" not in regular_event
    assert "X-APPLE-STRUCTURED-LOCATION" not in regular_event
