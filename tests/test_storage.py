"""Tests for storage layer."""

from datetime import datetime
from pathlib import Path
import tempfile
import shutil

import pytest

from app.config import CalendarConfig
from app.models.calendar import Calendar
from app.models.event import Event
from app.models.metadata import CalendarMetadata
from app.output.ics_writer import ICSWriter
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage


@pytest.fixture
def temp_calendar_dir():
    """Create a temporary calendar directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def repository(temp_calendar_dir):
    """Create a CalendarRepository for testing."""
    config = CalendarConfig()
    config.calendar_dir = temp_calendar_dir
    storage = CalendarStorage(config)
    return CalendarRepository(temp_calendar_dir, storage)


def test_calendar_storage_save(temp_calendar_dir):
    """Test CalendarStorage saves calendar files."""
    config = CalendarConfig()
    config.calendar_dir = temp_calendar_dir
    storage = CalendarStorage(config)

    events = [Event(title="Test", date=datetime(2025, 1, 1).date())]
    calendar = Calendar(events=events)
    writer = ICSWriter()

    filepath = storage.save_calendar(calendar, writer, temp_calendar_dir, "test_calendar")

    assert filepath.exists()
    assert filepath.suffix == ".ics"
    assert filepath.name == "calendar.ics"


def test_calendar_repository_save_and_load(repository):
    """Test CalendarRepository save and load operations."""
    events = [Event(title="Test Event", date=datetime(2025, 1, 1).date())]
    calendar = Calendar(events=events)

    metadata = CalendarMetadata(
        name="test_calendar",
        created=datetime.now(),
        last_updated=datetime.now(),
    )

    writer = ICSWriter()
    filepath = repository.save_calendar(calendar, metadata, writer)

    assert filepath.exists()

    # Load the calendar
    loaded = repository.load_calendar("test_calendar")
    assert loaded is not None
    assert len(loaded.calendar.events) == 1
    assert loaded.calendar.events[0].title == "Test Event"
    assert loaded.metadata.name == "test_calendar"


def test_calendar_repository_list_calendars(repository):
    """Test CalendarRepository list_calendars."""
    # Initially empty
    calendars = repository.list_calendars()
    assert len(calendars) == 0

    # Create a calendar
    events = [Event(title="Test", date=datetime(2025, 1, 1).date())]
    calendar = Calendar(events=events)
    metadata = CalendarMetadata(
        name="test_calendar",
        created=datetime.now(),
        last_updated=datetime.now(),
    )
    writer = ICSWriter()
    repository.save_calendar(calendar, metadata, writer)

    # Should now have one calendar
    calendars = repository.list_calendars()
    assert "test_calendar" in calendars


def test_calendar_repository_delete(repository):
    """Test CalendarRepository delete_calendar."""
    # Create a calendar
    events = [Event(title="Test", date=datetime(2025, 1, 1).date())]
    calendar = Calendar(events=events)
    metadata = CalendarMetadata(
        name="test_calendar",
        created=datetime.now(),
        last_updated=datetime.now(),
    )
    writer = ICSWriter()
    repository.save_calendar(calendar, metadata, writer)

    # Delete it
    repository.delete_calendar("test_calendar")

    # Should not be loadable
    loaded = repository.load_calendar("test_calendar")
    assert loaded is None

    # Should not be in list
    calendars = repository.list_calendars()
    assert "test_calendar" not in calendars


def test_calendar_repository_latest_detection(repository):
    """Test CalendarRepository calendar path detection."""
    events = [Event(title="Test", date=datetime(2025, 1, 1).date())]
    calendar = Calendar(events=events)
    metadata = CalendarMetadata(
        name="test_calendar",
        created=datetime.now(),
        last_updated=datetime.now(),
    )
    writer = ICSWriter()

    # Save calendar
    repository.save_calendar(calendar, metadata, writer)

    # Should return calendar.ics path
    latest_path = repository.get_latest_calendar_path("test_calendar", "ics")
    assert latest_path is not None
    assert latest_path.exists()
    assert latest_path.name == "calendar.ics"
