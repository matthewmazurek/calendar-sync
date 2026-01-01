"""Tests for storage layer."""

import subprocess
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

import pytest

from app.config import CalendarConfig
from app.exceptions import CalendarGitRepoNotFoundError
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
    # Initialize git repo in calendar_dir
    subprocess.run(["git", "init"], cwd=temp_calendar_dir, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_calendar_dir,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_calendar_dir,
        check=True,
    )
    
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
    latest_path = repository.get_calendar_path("test_calendar", "ics")
    assert latest_path is not None
    assert latest_path.exists()
    assert latest_path.name == "calendar.ics"


def test_calendar_repository_with_git_repo(temp_calendar_dir):
    """Test CalendarRepository when calendar_dir is a git repo."""
    # Initialize git repo in calendar_dir
    subprocess.run(["git", "init"], cwd=temp_calendar_dir, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_calendar_dir,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_calendar_dir,
        check=True,
    )

    config = CalendarConfig()
    config.calendar_dir = temp_calendar_dir
    storage = CalendarStorage(config)
    repository = CalendarRepository(temp_calendar_dir, storage)

    # Should not raise error
    assert repository.git_service.repo_root == temp_calendar_dir


def test_calendar_repository_without_git_repo(temp_calendar_dir):
    """Test CalendarRepository when calendar_dir is not a git repo."""
    # Create directory but don't initialize git
    temp_calendar_dir.mkdir(parents=True, exist_ok=True)

    config = CalendarConfig()
    config.calendar_dir = temp_calendar_dir
    storage = CalendarStorage(config)

    # Should raise CalendarGitRepoNotFoundError
    with pytest.raises(CalendarGitRepoNotFoundError) as exc_info:
        CalendarRepository(temp_calendar_dir, storage)
    
    assert "git-setup" in str(exc_info.value)


def test_calendar_repository_inside_source_repo(temp_calendar_dir):
    """Test CalendarRepository when calendar_dir is inside source repo."""
    # Create source repo
    source_repo = temp_calendar_dir.parent
    subprocess.run(["git", "init"], cwd=source_repo, check=True)
    
    # Create calendar_dir inside source repo
    calendar_dir = source_repo / "data" / "calendars"
    calendar_dir.mkdir(parents=True, exist_ok=True)

    config = CalendarConfig()
    config.calendar_dir = calendar_dir
    storage = CalendarStorage(config)

    # Should raise CalendarGitRepoNotFoundError because calendar_dir is not the repo root
    with pytest.raises(CalendarGitRepoNotFoundError) as exc_info:
        CalendarRepository(calendar_dir, storage)
    
    assert "git-setup" in str(exc_info.value)


def test_calendar_repository_nonexistent_dir(tmp_path):
    """Test CalendarRepository when calendar_dir doesn't exist yet."""
    calendar_dir = tmp_path / "nonexistent" / "calendars"

    config = CalendarConfig()
    config.calendar_dir = calendar_dir
    storage = CalendarStorage(config)

    # Should not raise error - allows directory to be created later
    repository = CalendarRepository(calendar_dir, storage)
    assert repository.git_service.repo_root == calendar_dir


def test_calendar_repository_with_remote_url(temp_calendar_dir):
    """Test CalendarRepository passes remote URL to GitPublisher."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=temp_calendar_dir, check=True)

    config = CalendarConfig()
    config.calendar_dir = temp_calendar_dir
    config.calendar_git_remote_url = "https://github.com/user/repo.git"
    storage = CalendarStorage(config)
    repository = CalendarRepository(temp_calendar_dir, storage)

    # GitPublisher should have remote URL
    assert repository.git_publisher.remote_url == "https://github.com/user/repo.git"
