"""Tests for ingestion layer."""

from datetime import date
from pathlib import Path

import pytest

from app.exceptions import IngestionError, InvalidYearError, UnsupportedFormatError
from app.ingestion.base import ReaderRegistry
from app.ingestion.ics_reader import ICSReader
from app.ingestion.json_reader import JSONReader
from app.ingestion.word_reader import TypeMatcher, WordReader
from app.models.calendar import Calendar
from app.models.event import Event
from app.models.template import CalendarTemplate, EventTypeConfig, TemplateDefaults


def test_reader_registry():
    """Test ReaderRegistry registration and retrieval."""
    registry = ReaderRegistry()
    word_reader = WordReader()
    registry.register(word_reader, [".doc", ".docx"])

    test_path = Path("test.docx")
    reader = registry.get_reader(test_path)
    assert reader == word_reader

    # Test unsupported format
    unsupported_path = Path("test.xyz")
    with pytest.raises(UnsupportedFormatError):
        registry.get_reader(unsupported_path)


def test_word_reader():
    """Test WordReader with example document."""
    fixture_path = Path(__file__).parent / "fixtures" / "example-calendar.docx"
    if not fixture_path.exists():
        pytest.skip("Fixture file not found")

    reader = WordReader()
    ingestion_result = reader.read(fixture_path)
    calendar = ingestion_result.calendar

    assert isinstance(calendar, Calendar)
    assert len(calendar.events) > 0
    assert calendar.year == 2025

    # Check that events are Event models
    assert all(isinstance(event, Event) for event in calendar.events)

    # Check that all events are from 2025
    assert all(event.date.year == 2025 for event in calendar.events)


def test_word_reader_single_year_validation():
    """Test that WordReader validates single year requirement."""
    fixture_path = Path(__file__).parent / "fixtures" / "example-calendar.docx"
    if not fixture_path.exists():
        pytest.skip("Fixture file not found")

    reader = WordReader()
    ingestion_result = reader.read(fixture_path)
    calendar = ingestion_result.calendar

    # Should have a single year
    years = {event.date.year for event in calendar.events}
    assert len(years) == 1


def test_ics_reader():
    """Test ICSReader with a simple ICS file."""
    # Create a simple ICS file
    ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
SUMMARY:Test Event
DTSTART:20250101T090000
DTEND:20250101T100000
END:VEVENT
END:VCALENDAR"""

    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ics", delete=False) as f:
        f.write(ics_content)
        temp_path = Path(f.name)

    try:
        reader = ICSReader()
        ingestion_result = reader.read(temp_path)
        calendar = ingestion_result.calendar

        assert isinstance(calendar, Calendar)
        assert len(calendar.events) == 1
        assert calendar.events[0].title == "Test Event"
        assert calendar.events[0].date == date(2025, 1, 1)
    finally:
        temp_path.unlink()


def test_ics_reader_empty_file():
    """Test ICSReader with non-existent file returns empty calendar."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".ics", delete=False) as f:
        temp_path = Path(f.name)
    temp_path.unlink()  # Delete the file

    reader = ICSReader()
    ingestion_result = reader.read(temp_path)
    calendar = ingestion_result.calendar

    assert isinstance(calendar, Calendar)
    assert len(calendar.events) == 0


def test_json_reader():
    """Test JSONReader with a simple JSON calendar."""
    import json
    import tempfile

    json_data = {
        "events": [
            {
                "title": "Test Event",
                "date": "2025-01-01",
                "start": "0900",
                "end": "1000",
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(json_data, f)
        temp_path = Path(f.name)

    try:
        reader = JSONReader()
        ingestion_result = reader.read(temp_path)
        calendar = ingestion_result.calendar

        assert isinstance(calendar, Calendar)
        assert len(calendar.events) == 1
        assert calendar.events[0].title == "Test Event"
    finally:
        temp_path.unlink()


def test_json_reader_invalid():
    """Test JSONReader with invalid JSON raises error."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("invalid json {")
        temp_path = Path(f.name)

    try:
        reader = JSONReader()
        with pytest.raises(IngestionError):
            reader.read(temp_path)
    finally:
        temp_path.unlink()


def test_time_period_expansion_defaults():
    """Test AM/PM expansion using default time periods."""
    template = CalendarTemplate(
        name="test",
        version="1.0",
        defaults=TemplateDefaults(
            time_periods={"AM": ("0800", "1200"), "PM": ("1300", "1700")}
        ),
        types={
            "clinic": EventTypeConfig(match="clinic"),
        },
    )

    matcher = TypeMatcher(template)

    # Test that clinic AM uses default AM times
    type_name, _ = matcher.match_type("Clinic AM")
    assert type_name == "clinic"
    start, end = matcher.resolve_time_periods("Clinic AM", type_name)
    assert start == "0800"
    assert end == "1200"

    # Test that clinic PM uses default PM times
    start, end = matcher.resolve_time_periods("Clinic PM", type_name)
    assert start == "1300"
    assert end == "1700"

    # Test case insensitivity
    start, end = matcher.resolve_time_periods("clinic am", type_name)
    assert start == "0800"
    assert end == "1200"

    # Test that text without AM/PM returns None
    start, end = matcher.resolve_time_periods("Clinic", type_name)
    assert start is None
    assert end is None


def test_time_period_expansion_type_specific():
    """Test AM/PM expansion using type-specific time periods."""
    template = CalendarTemplate(
        name="test",
        version="1.0",
        defaults=TemplateDefaults(
            time_periods={"AM": ("0800", "1200"), "PM": ("1300", "1700")}
        ),
        types={
            "ccsc": EventTypeConfig(
                match="ccsc",
                time_periods={"AM": ("0730", "1200"), "PM": ("1230", "1430")},
            ),
            "clinic": EventTypeConfig(match="clinic"),
        },
    )

    matcher = TypeMatcher(template)

    # Test that CCSC AM uses type-specific times
    type_name, _ = matcher.match_type("CCSC AM")
    assert type_name == "ccsc"
    start, end = matcher.resolve_time_periods("CCSC AM", type_name)
    assert start == "0730"
    assert end == "1200"

    # Test that CCSC PM uses type-specific times
    start, end = matcher.resolve_time_periods("CCSC PM", type_name)
    assert start == "1230"
    assert end == "1430"

    # Test that clinic still uses default times
    clinic_type, _ = matcher.match_type("Clinic AM")
    assert clinic_type == "clinic"
    start, end = matcher.resolve_time_periods("Clinic AM", clinic_type)
    assert start == "0800"  # Default AM time
    assert end == "1200"

    # Test that events without AM/PM return None
    start, end = matcher.resolve_time_periods("CCSC", type_name)
    assert start is None
    assert end is None


def test_time_period_expansion_no_type():
    """Test that time period expansion returns None when no type is matched."""
    template = CalendarTemplate(
        name="test",
        version="1.0",
        defaults=TemplateDefaults(
            time_periods={"AM": ("0800", "1200"), "PM": ("1300", "1700")}
        ),
        types={},
    )

    matcher = TypeMatcher(template)

    # Test with None type_name
    start, end = matcher.resolve_time_periods("Some Event AM", None)
    assert start is None
    assert end is None

    # Test with unmatched type
    type_name, _ = matcher.match_type("Unknown Event AM")
    assert type_name is None
    start, end = matcher.resolve_time_periods("Unknown Event AM", type_name)
    assert start is None
    assert end is None


def test_parse_cell_events_with_am_pm_expansion():
    """Test that events like 'CCSC AM' are parsed as timed events, not all-day."""
    from app.ingestion.word_reader import parse_cell_events

    template = CalendarTemplate(
        name="test",
        version="1.0",
        defaults=TemplateDefaults(
            time_periods={"AM": ("0800", "1200"), "PM": ("1300", "1700")}
        ),
        types={
            "ccsc": EventTypeConfig(
                match="ccsc",
                time_periods={"AM": ("0730", "1200"), "PM": ("1230", "1430")},
            ),
            "clinic": EventTypeConfig(match="clinic"),
        },
    )

    from app.ingestion.word_reader import TypeMatcher

    type_matcher = TypeMatcher(template)

    # Test CCSC AM - should be timed event with type-specific times
    events = parse_cell_events(
        "2 CCSC AM", month=2, year=2026, type_matcher=type_matcher
    )
    assert len(events) == 1
    assert events[0]["title"] == "CCSC AM"
    assert events[0]["date"] == "2026-02-02"
    assert events[0]["start"] == "0730"  # Type-specific AM time
    assert events[0]["end"] == "1200"
    assert events[0]["type"] == "ccsc"

    # Test CCSC PM - should be timed event with type-specific times
    events = parse_cell_events(
        "3 CCSC PM", month=2, year=2026, type_matcher=type_matcher
    )
    assert len(events) == 1
    assert events[0]["title"] == "CCSC PM"
    assert events[0]["date"] == "2026-02-03"
    assert events[0]["start"] == "1230"  # Type-specific PM time
    assert events[0]["end"] == "1430"
    assert events[0]["type"] == "ccsc"

    # Test Clinic AM - should be timed event with default times
    events = parse_cell_events(
        "4 Clinic AM", month=2, year=2026, type_matcher=type_matcher
    )
    assert len(events) == 1
    assert events[0]["title"] == "Clinic AM"
    assert events[0]["date"] == "2026-02-04"
    assert events[0]["start"] == "0800"  # Default AM time
    assert events[0]["end"] == "1200"
    assert events[0]["type"] == "clinic"

    # Test event without AM/PM - should be all-day (no start/end)
    events = parse_cell_events("5 CCSC", month=2, year=2026, type_matcher=type_matcher)
    assert len(events) == 1
    assert events[0]["title"] == "CCSC"
    assert events[0]["date"] == "2026-02-05"
    assert "start" not in events[0]  # All-day event
    assert "end" not in events[0]
    assert events[0]["type"] == "ccsc"
