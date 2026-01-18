"""Tests for ingestion layer."""

from datetime import date
from pathlib import Path

import pytest

from app.exceptions import IngestionError, InvalidYearError, UnsupportedFormatError
from app.ingestion.base import ReaderRegistry
from app.ingestion.ics_reader import ICSReader
from app.ingestion.json_reader import JSONReader
from app.ingestion.word_reader import TypeMatcher, WordReader
from app.models.event import Event
from app.models.ingestion import RawIngestion
from app.models.template import CalendarTemplate, EventTypeConfig, TemplateDefaults
from app.processing.merge_strategies import infer_year


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
    raw = ingestion_result.raw

    assert isinstance(raw, RawIngestion)
    assert len(raw.events) > 0
    
    # Infer year from events
    year = infer_year(raw.events)
    assert year == 2025

    # Check that events are Event models
    assert all(isinstance(event, Event) for event in raw.events)

    # Check that all events are from 2025
    assert all(event.date.year == 2025 for event in raw.events)


def test_word_reader_single_year_validation():
    """Test that WordReader validates single year requirement."""
    fixture_path = Path(__file__).parent / "fixtures" / "example-calendar.docx"
    if not fixture_path.exists():
        pytest.skip("Fixture file not found")

    reader = WordReader()
    ingestion_result = reader.read(fixture_path)
    raw = ingestion_result.raw

    # Should have a single year
    years = {event.date.year for event in raw.events}
    assert len(years) == 1


def test_ics_reader():
    """Test ICSReader with a simple ICS file."""
    # Create a simple ICS file
    ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:test-uid-123
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
        raw = ingestion_result.raw

        assert isinstance(raw, RawIngestion)
        assert len(raw.events) == 1
        assert raw.events[0].title == "Test Event"
        assert raw.events[0].date == date(2025, 1, 1)
        # Check UID is extracted
        assert raw.events[0].uid == "test-uid-123"
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
    raw = ingestion_result.raw

    assert isinstance(raw, RawIngestion)
    assert len(raw.events) == 0


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
        raw = ingestion_result.raw

        assert isinstance(raw, RawIngestion)
        assert len(raw.events) == 1
        assert raw.events[0].title == "Test Event"
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


def test_parse_cell_events_multiple_time_ranges():
    """Test that events with multiple time ranges are split into separate events."""
    from app.ingestion.word_reader import parse_cell_events, TypeMatcher

    template = CalendarTemplate(
        name="test",
        version="1.0",
        defaults=TemplateDefaults(),
        types={
            "ccsc": EventTypeConfig(match="ccsc"),
            "clinic": EventTypeConfig(match="clinic"),
        },
    )

    type_matcher = TypeMatcher(template)

    # Test "CCSC 0730-1200 and 1230-1630" - should create 2 events
    events = parse_cell_events(
        "15 CCSC 0730-1200 and 1230-1630", month=1, year=2026, type_matcher=type_matcher
    )
    assert len(events) == 2
    assert events[0]["title"] == "CCSC"
    assert events[0]["date"] == "2026-01-15"
    assert events[0]["start"] == "0730"
    assert events[0]["end"] == "1200"
    assert events[0]["type"] == "ccsc"
    assert events[1]["title"] == "CCSC"
    assert events[1]["date"] == "2026-01-15"
    assert events[1]["start"] == "1230"
    assert events[1]["end"] == "1630"
    assert events[1]["type"] == "ccsc"

    # Test with "&" conjunction
    events = parse_cell_events(
        "16 Clinic 0900-1100 & 1300-1500", month=1, year=2026, type_matcher=type_matcher
    )
    assert len(events) == 2
    assert events[0]["title"] == "Clinic"
    assert events[0]["start"] == "0900"
    assert events[0]["end"] == "1100"
    assert events[1]["title"] == "Clinic"
    assert events[1]["start"] == "1300"
    assert events[1]["end"] == "1500"

    # Test with "+" conjunction
    events = parse_cell_events(
        "17 CCSC 0800-1000 + 1400-1600", month=1, year=2026, type_matcher=type_matcher
    )
    assert len(events) == 2
    assert events[0]["title"] == "CCSC"
    assert events[0]["start"] == "0800"
    assert events[0]["end"] == "1000"
    assert events[1]["title"] == "CCSC"
    assert events[1]["start"] == "1400"
    assert events[1]["end"] == "1600"

    # Test without conjunction - should create single event
    events = parse_cell_events(
        "18 CCSC 0730-1200", month=1, year=2026, type_matcher=type_matcher
    )
    assert len(events) == 1
    assert events[0]["title"] == "CCSC"
    assert events[0]["start"] == "0730"
    assert events[0]["end"] == "1200"


def test_parse_cell_events_multiple_periods():
    """Test that events like 'CCSC AM and PM' are split into separate events."""
    from app.ingestion.word_reader import parse_cell_events, TypeMatcher

    template = CalendarTemplate(
        name="test",
        version="1.0",
        defaults=TemplateDefaults(
            time_periods={"AM": ("0800", "1200"), "PM": ("1300", "1700")}
        ),
        types={
            "ccsc": EventTypeConfig(
                match="ccsc",
                time_periods={"AM": ("0730", "1200"), "PM": ("1230", "1630")},
            ),
        },
    )

    type_matcher = TypeMatcher(template)

    # Test "CCSC AM and PM" - should create 2 events
    events = parse_cell_events(
        "20 CCSC AM and PM", month=1, year=2026, type_matcher=type_matcher
    )
    assert len(events) == 2
    assert events[0]["title"] == "CCSC"
    assert events[0]["date"] == "2026-01-20"
    assert events[0]["start"] == "0730"  # Type-specific AM
    assert events[0]["end"] == "1200"
    assert events[0]["type"] == "ccsc"
    assert events[1]["title"] == "CCSC"
    assert events[1]["date"] == "2026-01-20"
    assert events[1]["start"] == "1230"  # Type-specific PM
    assert events[1]["end"] == "1630"
    assert events[1]["type"] == "ccsc"

    # Test with "&" conjunction
    events = parse_cell_events(
        "21 CCSC AM & PM", month=1, year=2026, type_matcher=type_matcher
    )
    assert len(events) == 2
    assert events[0]["start"] == "0730"
    assert events[1]["start"] == "1230"

    # Test with "+" conjunction
    events = parse_cell_events(
        "22 CCSC AM + PM", month=1, year=2026, type_matcher=type_matcher
    )
    assert len(events) == 2
    assert events[0]["start"] == "0730"
    assert events[1]["start"] == "1230"
