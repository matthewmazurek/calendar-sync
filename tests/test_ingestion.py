"""Tests for ingestion layer."""

from datetime import date
from pathlib import Path

import pytest

from app.exceptions import IngestionError, InvalidYearError, UnsupportedFormatError
from app.ingestion.base import ReaderRegistry
from app.ingestion.ics_reader import ICSReader
from app.ingestion.json_reader import JSONReader
from app.ingestion.word_reader import WordReader
from app.models.calendar import Calendar
from app.models.event import Event


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
    calendar = reader.read(fixture_path)

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
    calendar = reader.read(fixture_path)

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
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ics', delete=False) as f:
        f.write(ics_content)
        temp_path = Path(f.name)

    try:
        reader = ICSReader()
        calendar = reader.read(temp_path)

        assert isinstance(calendar, Calendar)
        assert len(calendar.events) == 1
        assert calendar.events[0].title == "Test Event"
        assert calendar.events[0].date == date(2025, 1, 1)
    finally:
        temp_path.unlink()


def test_ics_reader_empty_file():
    """Test ICSReader with non-existent file returns empty calendar."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.ics', delete=False) as f:
        temp_path = Path(f.name)
    temp_path.unlink()  # Delete the file

    reader = ICSReader()
    calendar = reader.read(temp_path)

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
                "end": "1000"
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(json_data, f)
        temp_path = Path(f.name)

    try:
        reader = JSONReader()
        calendar = reader.read(temp_path)

        assert isinstance(calendar, Calendar)
        assert len(calendar.events) == 1
        assert calendar.events[0].title == "Test Event"
    finally:
        temp_path.unlink()


def test_json_reader_invalid():
    """Test JSONReader with invalid JSON raises error."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("invalid json {")
        temp_path = Path(f.name)

    try:
        reader = JSONReader()
        with pytest.raises(IngestionError):
            reader.read(temp_path)
    finally:
        temp_path.unlink()
