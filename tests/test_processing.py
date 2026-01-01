"""Tests for processing layer with Pydantic models."""

from datetime import date, datetime, time
from pathlib import Path
import tempfile
import shutil

import pytest

from app.config import CalendarConfig
from app.models.calendar import Calendar
from app.models.event import Event, EventType
from app.processing.calendar_manager import CalendarManager
from app.processing.event_processor import process_events
from app.processing.event_type_processors import (
    AllDayEventProcessor,
    OnCallEventProcessor,
    RegularEventProcessor,
)
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage


def test_oncall_processor():
    """Test on-call event processor."""
    processor = OnCallEventProcessor()
    events = [
        Event(title="Primary on call", date=date(2025, 1, 1), start=time(8, 0), end=time(17, 0)),
        Event(title="Primary on call", date=date(2025, 1, 2), start=time(8, 0), end=time(17, 0)),
    ]

    processed = processor.process(events)
    assert len(processed) == 1
    assert processed[0].end_date == date(2025, 1, 2)
    assert processed[0].is_all_day is True


def test_allday_processor():
    """Test all-day event processor."""
    processor = AllDayEventProcessor()
    events = [
        Event(title="Holiday", date=date(2025, 1, 1)),
        Event(title="Holiday", date=date(2025, 1, 2)),
    ]

    processed = processor.process(events)
    assert len(processed) == 1
    assert processed[0].end_date == date(2025, 1, 2)


def test_regular_processor():
    """Test regular event processor."""
    processor = RegularEventProcessor()
    events = [
        Event(title="Clinic", date=date(2025, 1, 1), start=time(9, 0), end=time(10, 0)),
    ]

    processed = processor.process(events)
    assert len(processed) == 1
    assert processed[0].location is not None


def test_process_events_pipeline():
    """Test event processing pipeline."""
    events = [
        Event(title="Primary on call", date=date(2025, 1, 1), start=time(8, 0), end=time(17, 0)),
        Event(title="Clinic", date=date(2025, 1, 2), start=time(9, 0), end=time(10, 0)),
        Event(title="Holiday", date=date(2025, 1, 3)),
    ]

    processed, summary = process_events(events)
    assert len(processed) >= 1
    # On-call should be consolidated
    oncall_events = [e for e in processed if e.type == EventType.ON_CALL]
    assert len(oncall_events) == 1


def test_source_revised_at_extraction():
    """Test that source_revised_at is extracted from source Calendar."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        config = CalendarConfig()
        config.calendar_dir = temp_dir
        storage = CalendarStorage(config)
        repository = CalendarRepository(temp_dir, storage)
        manager = CalendarManager(repository)

        # Create source calendar with revised_date
        revised_date = date(2025, 12, 16)
        events = [Event(title="Test Event", date=date(2025, 1, 1))]
        source_calendar = Calendar(events=events, revised_date=revised_date, year=2025)

        # Create calendar from source
        result, _ = manager.create_calendar_from_source(source_calendar, "test_calendar")

        # Verify source_revised_at is set in metadata
        assert result.metadata.source_revised_at == revised_date

        # Save the calendar so it exists for composition
        from app.output.ics_writer import ICSWriter
        writer = ICSWriter()
        repository.save_calendar(result.calendar, result.metadata, writer)

        # Test compose with new source that has revised_date
        new_revised_date = date(2025, 12, 20)
        new_source = Calendar(events=events, revised_date=new_revised_date, year=2025)
        composed, _ = manager.compose_calendar_with_source(
            "test_calendar", new_source, 2025, repository
        )

        # Verify source_revised_at is updated
        assert composed.metadata.source_revised_at == new_revised_date

        # Save the composed calendar so it exists for the next compose
        repository.save_calendar(composed.calendar, composed.metadata, writer)

        # Test compose with source that has no revised_date
        source_no_revised = Calendar(events=events, year=2025)
        composed2, _ = manager.compose_calendar_with_source(
            "test_calendar", source_no_revised, 2025, repository
        )

        # Verify source_revised_at is preserved from previous
        assert composed2.metadata.source_revised_at == new_revised_date
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
