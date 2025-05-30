import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from flask import Flask

from app.calendar_storage import (
    DEFAULT_CALENDAR_DIR,
    DEFAULT_RETENTION_DAYS,
    cleanup_old_calendars,
    get_calendar_dir,
    get_latest_calendar,
    get_retention_days,
    save_calendar,
)


@pytest.fixture
def app():
    """Create a Flask app for testing."""
    app = Flask(__name__)
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app


@pytest.fixture
def sample_ical_content():
    return b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Calendar Sync//EN
BEGIN:VEVENT
SUMMARY:Test Event
DTSTART:20240101T120000
DTEND:20240101T130000
END:VEVENT
END:VCALENDAR"""


@pytest.fixture(autouse=True)
def cleanup_calendar_dir():
    """Clean up calendar directory before and after each test."""
    if DEFAULT_CALENDAR_DIR.exists():
        for file in DEFAULT_CALENDAR_DIR.glob("*"):
            if file.is_file():
                file.unlink()
        DEFAULT_CALENDAR_DIR.rmdir()
    yield
    if DEFAULT_CALENDAR_DIR.exists():
        for file in DEFAULT_CALENDAR_DIR.glob("*"):
            if file.is_file():
                file.unlink()
        DEFAULT_CALENDAR_DIR.rmdir()


def test_default_config(app):
    """Test default configuration values."""
    with app.app_context():
        assert get_calendar_dir() == DEFAULT_CALENDAR_DIR
        assert get_retention_days() == DEFAULT_RETENTION_DAYS


def test_custom_config(app):
    """Test custom configuration values."""
    custom_dir = Path("/tmp/custom_calendars")
    custom_retention = 60

    app.config.update(
        {
            "CALENDAR_DIR": str(custom_dir),
            "CALENDAR_RETENTION_DAYS": custom_retention,
        }
    )

    with app.app_context():
        assert get_calendar_dir() == custom_dir
        assert get_retention_days() == custom_retention


def test_save_calendar(app, sample_ical_content):
    """Test saving a calendar file."""
    with app.app_context():
        filename = save_calendar(sample_ical_content)

        # Check that the file was created
        assert get_calendar_dir().exists()
        assert (get_calendar_dir() / filename).exists()

        # Check that the latest file was created
        latest_path = get_calendar_dir() / "latest-calendar.ics"
        assert latest_path.exists()

        # Check that latest is a copy, not a symlink
        assert not latest_path.is_symlink()

        # Check file contents
        with open(latest_path, "rb") as f:
            content = f.read()
        assert content == sample_ical_content


def test_get_latest_calendar(app, sample_ical_content):
    """Test retrieving the latest calendar."""
    with app.app_context():
        # Should return None when no calendar exists
        assert get_latest_calendar() is None

        # Save a calendar and check it can be retrieved
        save_calendar(sample_ical_content)
        content = get_latest_calendar()
        assert content == sample_ical_content


def test_multiple_calendars(app, sample_ical_content):
    """Test handling multiple calendar files."""
    with app.app_context():
        # Save first calendar
        filename1 = save_calendar(sample_ical_content)

        # Save second calendar with different content
        modified_content = sample_ical_content.replace(b"Test Event", b"Modified Event")
        filename2 = save_calendar(modified_content)

        # Check that both files exist
        assert (get_calendar_dir() / filename1).exists()
        assert (get_calendar_dir() / filename2).exists()

        # Check that latest points to the second file
        latest_content = get_latest_calendar()
        assert latest_content == modified_content


def test_cleanup_old_calendars(app, sample_ical_content):
    """Test cleanup of old calendar files."""
    with app.app_context():
        # Set a short retention period
        app.config["CALENDAR_RETENTION_DAYS"] = 1

        # Create some old files
        old_date = datetime.now() - timedelta(days=2)
        old_filename = f"calendar_{old_date.strftime('%Y%m%d_%H%M%S')}.ics"
        old_path = get_calendar_dir() / old_filename
        get_calendar_dir().mkdir(parents=True, exist_ok=True)
        with open(old_path, "wb") as f:
            f.write(sample_ical_content)

        # Create a new file
        new_filename = save_calendar(sample_ical_content)

        # Run cleanup
        cleanup_old_calendars()

        # Check that old file was removed but new file remains
        assert not old_path.exists()
        assert (get_calendar_dir() / new_filename).exists()
