from datetime import datetime, timedelta

import pytest

from app.event_processor import (
    WORK_LOCATION,
    consolidate_oncall_events,
    include_work_location,
    process_events,
    process_overnight_event,
)


def test_consolidate_consecutive_oncall_events():
    """Test that consecutive on-call events of the same type are consolidated."""
    events = [
        # Primary on-call sequence with different times
        {
            "title": "Primary on call",
            "date": "2025-01-01",
            "start": "0700",
            "end": "1900",
        },
        {
            "title": "Primary on call",
            "date": "2025-01-02",
            "start": "0800",  # Different start time
            "end": "2000",  # Different end time
        },
        {
            "title": "Primary on call",
            "date": "2025-01-03",
            "start": "0730",  # Different start time
            "end": "1930",  # Different end time
        },
        # Endo on-call sequence with different times
        {
            "title": "Endo on call",
            "date": "2025-01-04",
            "start": "0700",
            "end": "1900",
        },
        {
            "title": "Endo on call",
            "date": "2025-01-05",
            "start": "0800",  # Different start time
            "end": "2000",  # Different end time
        },
        # Regular event (should be unchanged)
        {
            "title": "Regular Meeting",
            "date": "2025-01-06",
            "start": "0900",
            "end": "1000",
        },
        # Another primary on-call sequence
        {
            "title": "Primary on call",
            "date": "2025-01-07",
            "start": "0700",
            "end": "1900",
        },
        {
            "title": "Primary on call",
            "date": "2025-01-08",
            "start": "0800",  # Different start time
            "end": "2000",  # Different end time
        },
    ]

    processed = consolidate_oncall_events(events)

    # Should have 4 events: 2 consolidated on-call sequences, 1 consolidated endo event, and 1 regular event
    assert len(processed) == 4

    # Find the consolidated events
    primary_events = [e for e in processed if e["title"] == "Primary on call"]
    endo_events = [e for e in processed if e["title"] == "Endo on call"]
    regular_events = [e for e in processed if e["title"] == "Regular Meeting"]

    # Check primary on-call consolidation
    assert len(primary_events) == 2  # Two separate sequences
    primary1 = next(e for e in primary_events if e["date"] == "2025-01-01")
    primary2 = next(e for e in primary_events if e["date"] == "2025-01-07")
    assert primary1["end_date"] == "2025-01-03"
    assert primary2["end_date"] == "2025-01-08"
    # Multi-day events should be all-day events
    assert "start" not in primary1
    assert "end" not in primary1
    assert "start" not in primary2
    assert "end" not in primary2

    # Check endo on-call consolidation
    assert len(endo_events) == 1
    endo = endo_events[0]
    assert endo["date"] == "2025-01-04"
    assert endo["end_date"] == "2025-01-05"
    # Multi-day events should be all-day events
    assert "start" not in endo
    assert "end" not in endo

    # Check regular event is unchanged
    assert len(regular_events) == 1
    regular = regular_events[0]
    assert regular["date"] == "2025-01-06"
    assert "end_date" not in regular
    assert regular["start"] == "0900"
    assert regular["end"] == "1000"


def test_consolidate_oncall_events():
    events = [
        {
            "title": "Primary on call",
            "date": "2025-01-01",
            "start": "0800",
            "end": "0800",
        },
        {
            "title": "Primary on call",
            "date": "2025-01-02",
            "start": "0800",
            "end": "1700",
        },
        {
            "title": "Primary on call",
            "date": "2025-01-03",
            "start": "0800",
            "end": "0800",
        },
        {
            "title": "Primary on call",
            "date": "2025-01-04",
            "start": "0800",
            "end": "1700",
        },
    ]
    processed = consolidate_oncall_events(events)
    assert (
        len(processed) == 3
    )  # 3 events, 1 multi-day event (2025-01-01 to 2025-01-04), 2 overnight events (2025-01-01 and 2025-01-03)


def test_consolidate_oncall_events_with_gaps():
    """Test that on-call events with gaps are not consolidated."""
    events = [
        {
            "title": "Primary on call",
            "date": "2025-01-01",
            "start": "0700",
            "end": "1900",
        },
        {
            "title": "Primary on call",
            "date": "2025-01-03",  # Gap on Jan 2
            "start": "0800",  # Different start time
            "end": "2000",  # Different end time
        },
    ]

    processed = consolidate_oncall_events(events)
    assert len(processed) == 2  # Should not consolidate due to gap


def test_consolidate_oncall_events_with_different_end_times():
    """Test that on-call events with different times are consolidated."""
    events = [
        {
            "title": "Primary on call",
            "date": "2025-01-01",
            "start": "0700",
            "end": "1900",
        },
        {
            "title": "Primary on call",
            "date": "2025-01-02",
            "start": "0800",
            "end": "2000",  # Different end time
        },
    ]

    processed = consolidate_oncall_events(events)
    assert len(processed) == 1  # Should consolidate due to same start time
    assert processed[0]["date"] == "2025-01-01"
    assert processed[0]["end_date"] == "2025-01-02"
    # Multi-day events should be all-day events
    assert "start" not in processed[0]
    assert "end" not in processed[0]


def test_process_overnight_event():
    """Test that overnight events are correctly converted to all-day events with readable time ranges."""
    # Test case 1: Same start and end time (e.g., 0800-0800)
    event1 = {
        "title": "Primary on call 0800-0800",
        "date": "2025-01-01",
        "start": "0800",
        "end": "0800",
    }
    processed1 = process_overnight_event(event1)
    assert processed1["title"] == "Primary on call 8:00 AM to 8:00 AM"
    assert "start" not in processed1
    assert "end" not in processed1

    # Test case 2: End time earlier than start time (e.g., 1700-0800)
    event2 = {
        "title": "Primary on call 1700-0800",
        "date": "2025-01-01",
        "start": "1700",
        "end": "0800",
    }
    processed2 = process_overnight_event(event2)
    assert processed2["title"] == "Primary on call 5:00 PM to 8:00 AM"
    assert "start" not in processed2
    assert "end" not in processed2

    # Test case 3: Not an overnight event (should be unchanged)
    event3 = {
        "title": "Primary on call 0800-1700",
        "date": "2025-01-01",
        "start": "0800",
        "end": "1700",
    }
    processed3 = process_overnight_event(event3)
    assert processed3 == event3  # Should be unchanged

    # Test case 4: No start/end times (should be unchanged)
    event4 = {
        "title": "Primary on call",
        "date": "2025-01-01",
    }
    processed4 = process_overnight_event(event4)
    assert processed4 == event4  # Should be unchanged


def test_work_location_added_to_all_events():
    """Test that the work location is added to all events."""
    events = [
        {
            "title": "Primary on call",
            "date": "2025-01-01",
            "start": "0700",
            "end": "1900",
        },
        {
            "title": "Regular Meeting",
            "date": "2025-01-02",
            "start": "0900",
            "end": "1000",
        },
        {
            "title": "On call 0800-0800",
            "date": "2025-01-03",
            "start": "0800",
            "end": "0800",
        },
    ]

    processed = process_events(events)

    # Check that all events that should have the work location do, and others do not
    for event in processed:
        if "on call" in event["title"].lower():
            assert event["location"] == WORK_LOCATION
        else:
            assert "location" not in event


def test_include_work_location():
    """Test that work location is correctly determined based on event title."""
    # Events that should have work location
    assert include_work_location("Endo") == WORK_LOCATION
    assert include_work_location("CCSC") == WORK_LOCATION
    assert include_work_location("Clinic") == WORK_LOCATION
    assert include_work_location("Primary on call") == WORK_LOCATION
    assert include_work_location("ENDO ON CALL") == WORK_LOCATION  # Case insensitive

    # Events that should not have work location
    assert include_work_location("Admin day") is None
    assert include_work_location("New Year's Day") is None
    assert include_work_location("CDDW") is None
