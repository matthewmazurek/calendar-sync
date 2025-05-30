import re
from pathlib import Path

import pytest

from app.calendar_parser import parse_docx_events


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
    fixture_path = Path(__file__).parent / "fixtures" / "example-calendar.docx"
    events = parse_docx_events(fixture_path)

    # Helper to find an event by date and title substring
    def has_event(date, title_substring, start=None, end=None):
        norm_sub = normalize_text(title_substring)
        for event in events:
            if event["date"] == date and norm_sub in normalize_text(event["title"]):
                if start and event.get("start") != start:
                    continue
                if end and event.get("end") != end:
                    continue
                return True
        return False

    # Test all-day events
    assert has_event("2025-01-01", "New Year's Day")  # Holiday
    assert has_event("2025-01-08", "ADMIN DAY")  # Admin day

    # Test timed events
    assert has_event("2025-01-03", "CCSC", start="0730", end="1200")
    assert has_event("2025-01-03", "Emergent Endo", start="1230", end="1630")

    # Test a cell with multiple events (both all-day and timed)
    assert has_event("2025-12-22", "Hanukkah ends")  # All-day event
    assert has_event("2025-12-22", "Post Call")  # All-day event

    # Test on-call events
    assert has_event("2025-01-28", "Endo on call", start="0730", end="1630")
    assert has_event("2025-01-28", "on call", start="1700", end="0800")


def test_parser_extracts_year_from_document():
    """Test that the parser extracts the year from the document content."""
    fixture_path = Path(__file__).parent / "fixtures" / "example-calendar.docx"
    events = parse_docx_events(fixture_path)

    # Verify that all events are from 2025
    for event in events:
        year = int(event["date"].split("-")[0])
        assert year == 2025, f"Event date {event['date']} should be from 2025"
