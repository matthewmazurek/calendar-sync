"""Tests for processing layer with merge strategies."""

import shutil
import subprocess
import tempfile
from datetime import date, datetime
from pathlib import Path

from app import setup_reader_registry
from app.config import CalendarConfig
from app.models.calendar import Calendar
from app.models.event import Event
from app.models.ingestion import RawIngestion
from app.processing.calendar_manager import CalendarManager
from app.processing.merge_strategies import (
    Add,
    ReplaceByYear,
    UpsertById,
    infer_year,
    merge_events,
)
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage
from app.storage.git_service import GitService


def make_calendar(events: list[Event], name: str = "test") -> Calendar:
    """Helper to create a Calendar with default metadata."""
    now = datetime.now()
    return Calendar(
        events=events,
        name=name,
        created=now,
        last_updated=now,
    )


def test_source_revised_at_extraction():
    """Test that source_revised_at is extracted from source data."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=temp_dir, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_dir,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_dir,
            check=True,
        )

        config = CalendarConfig()
        config.calendar_dir = temp_dir
        storage = CalendarStorage(config)
        git_service = GitService(temp_dir)
        reader_registry = setup_reader_registry()
        repository = CalendarRepository(temp_dir, storage, git_service, reader_registry)
        manager = CalendarManager(repository)

        # Create source with revised_at
        revised_date = date(2025, 12, 16)
        events = [Event(title="Test Event", date=date(2025, 1, 1))]
        raw = RawIngestion(events=events, revised_at=revised_date)

        # Create calendar from raw ingestion
        result = manager.create_calendar("test_calendar", raw)

        # Verify source_revised_at is set
        assert result.calendar.source_revised_at == revised_date

        # Save the calendar so it exists for update
        repository.save(result.calendar)

        # Test update with new source that has revised_at
        new_revised_date = date(2025, 12, 20)
        new_raw = RawIngestion(events=events, revised_at=new_revised_date)
        updated_result = manager.update_calendar(
            "test_calendar", new_raw, ReplaceByYear(2025)
        )

        # Verify source_revised_at is updated
        assert updated_result.calendar.source_revised_at == new_revised_date

        # Save the updated calendar
        repository.save(updated_result.calendar)

        # Test update with source that has no revised_at
        raw_no_revised = RawIngestion(events=events)
        updated_result2 = manager.update_calendar(
            "test_calendar", raw_no_revised, ReplaceByYear(2025)
        )

        # Verify source_revised_at is preserved from previous
        assert updated_result2.calendar.source_revised_at == new_revised_date
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_merge_events_replace_by_year():
    """Test ReplaceByYear merge strategy."""
    existing = [
        Event(title="Event 2024", date=date(2024, 1, 1)),
        Event(title="Event 2025 A", date=date(2025, 1, 1)),
        Event(title="Event 2025 B", date=date(2025, 6, 1)),
    ]
    new = [
        Event(title="New Event 2025", date=date(2025, 3, 1)),
    ]

    result = merge_events(existing, new, ReplaceByYear(2025))

    # Should keep 2024 events and replace 2025 events
    assert len(result) == 2
    titles = {e.title for e in result}
    assert "Event 2024" in titles
    assert "New Event 2025" in titles
    assert "Event 2025 A" not in titles
    assert "Event 2025 B" not in titles


def test_merge_events_add():
    """Test Add merge strategy."""
    existing = [
        Event(title="Existing Event", date=date(2025, 1, 1)),
    ]
    new = [
        Event(title="New Event", date=date(2025, 2, 1)),
    ]

    result = merge_events(existing, new, Add())

    # Should have both events
    assert len(result) == 2
    titles = {e.title for e in result}
    assert "Existing Event" in titles
    assert "New Event" in titles


def test_merge_events_upsert_by_id():
    """Test UpsertById merge strategy."""
    existing = [
        Event(title="Event 1", date=date(2025, 1, 1), uid="uid-1"),
        Event(title="Event 2", date=date(2025, 2, 1), uid="uid-2"),
        Event(title="Event No UID", date=date(2025, 3, 1)),
    ]
    new = [
        Event(title="Event 1 Updated", date=date(2025, 1, 15), uid="uid-1"),  # Update
        Event(title="New Event", date=date(2025, 4, 1), uid="uid-3"),  # Insert
    ]

    result = merge_events(existing, new, UpsertById())

    # Should have 4 events: updated uid-1, kept uid-2, kept no-uid, new uid-3
    assert len(result) == 4
    
    # Check that uid-1 was updated
    uid1_events = [e for e in result if e.uid == "uid-1"]
    assert len(uid1_events) == 1
    assert uid1_events[0].title == "Event 1 Updated"
    assert uid1_events[0].date == date(2025, 1, 15)
    
    # Check that uid-2 was kept
    uid2_events = [e for e in result if e.uid == "uid-2"]
    assert len(uid2_events) == 1
    assert uid2_events[0].title == "Event 2"
    
    # Check that new uid-3 was added
    uid3_events = [e for e in result if e.uid == "uid-3"]
    assert len(uid3_events) == 1
    assert uid3_events[0].title == "New Event"


def test_infer_year_single():
    """Test year inference with single year."""
    events = [
        Event(title="Event 1", date=date(2025, 1, 1)),
        Event(title="Event 2", date=date(2025, 12, 31)),
    ]
    assert infer_year(events) == 2025


def test_infer_year_multiple():
    """Test year inference with multiple years returns None."""
    events = [
        Event(title="Event 1", date=date(2025, 1, 1)),
        Event(title="Event 2", date=date(2026, 1, 1)),
    ]
    assert infer_year(events) is None


def test_infer_year_empty():
    """Test year inference with empty list returns None."""
    assert infer_year([]) is None
