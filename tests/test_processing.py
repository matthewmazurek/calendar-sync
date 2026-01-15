"""Tests for processing layer with Pydantic models."""

import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from app import setup_reader_registry
from app.config import CalendarConfig
from app.models.calendar import Calendar
from app.models.event import Event
from app.processing.calendar_manager import CalendarManager
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage
from app.storage.git_service import GitService


def test_source_revised_at_extraction():
    """Test that source_revised_at is extracted from source Calendar."""
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

        # Create source calendar with revised_date
        revised_date = date(2025, 12, 16)
        events = [Event(title="Test Event", date=date(2025, 1, 1))]
        source_calendar = Calendar(events=events, revised_date=revised_date, year=2025)

        # Create calendar from source
        result, _ = manager.create_calendar_from_source(
            source_calendar, "test_calendar"
        )

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
