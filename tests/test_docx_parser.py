"""Tests for Word document parsing using new ingestion layer."""

import re
from datetime import datetime
from pathlib import Path

import pytest

from app.ingestion.word_reader import WordReader
from app.models.event import Event


def normalize_text(s):
    # Replace curly apostrophes and quotes with straight ones
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace(""", '"').replace(""", '"')
    # Remove invisible/directional marks
    s = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def test_parse_example_calendar():
    """Test parsing example calendar using WordReader."""
    fixture_path = Path(__file__).parent / "fixtures" / "example-calendar.docx"
    if not fixture_path.exists():
        pytest.skip("Fixture file not found")

    reader = WordReader()
    ingestion_result = reader.read(fixture_path)
    calendar = ingestion_result.calendar
    events = calendar.events

    # Helper to find an event by date and title substring
    def has_event(date_str, title_substring, start_str=None, end_str=None):
        norm_sub = normalize_text(title_substring)
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        for event in events:
            if event.date == target_date and norm_sub in normalize_text(event.title):
                if start_str and event.start:
                    start_str_actual = event.start.strftime("%H%M")
                    if start_str_actual != start_str:
                        continue
                if end_str and event.end:
                    end_str_actual = event.end.strftime("%H%M")
                    if end_str_actual != end_str:
                        continue
                return True
        return False

    from datetime import datetime

    # Test all-day events
    assert has_event("2025-01-01", "New Year's Day")  # Holiday
    assert has_event("2025-01-08", "ADMIN DAY")  # Admin day

    # Test timed events
    assert has_event("2025-01-03", "CCSC", start_str="0730", end_str="1200")
    assert has_event("2025-01-03", "Emergent Endo", start_str="1230", end_str="1630")

    # Test a cell with multiple events (both all-day and timed)
    assert has_event("2025-12-22", "Hanukkah ends")  # All-day event
    assert has_event("2025-12-22", "Post Call")  # All-day event

    # Test on-call events
    assert has_event("2025-01-28", "Endo on call", start_str="0730", end_str="1630")
    assert has_event("2025-01-28", "on call", start_str="1700", end_str="0800")


def test_parser_extracts_year_from_document():
    """Test that the parser extracts the year from the document content."""
    fixture_path = Path(__file__).parent / "fixtures" / "example-calendar.docx"
    if not fixture_path.exists():
        pytest.skip("Fixture file not found")

    reader = WordReader()
    ingestion_result = reader.read(fixture_path)
    calendar = ingestion_result.calendar

    # Verify that calendar has year set
    assert calendar.year == 2025

    # Verify that all events are from 2025
    for event in calendar.events:
        assert event.date.year == 2025, f"Event date {event.date} should be from 2025"
