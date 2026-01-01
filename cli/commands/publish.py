"""Publish an existing calendar to git."""

import logging
import sys

from app.config import CalendarConfig
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage
from app.storage.git_service import GitService
from cli.setup import setup_reader_registry

logger = logging.getLogger(__name__)


def publish_command(calendar_name: str, format: str = "ics") -> None:
    """Publish an existing calendar to git."""
    config = CalendarConfig.from_env()
    storage = CalendarStorage(config)
    reader_registry = setup_reader_registry()
    git_service = GitService(
        config.calendar_dir,
        remote_url=config.calendar_git_remote_url,
    )
    repository = CalendarRepository(
        config.calendar_dir, storage, git_service, reader_registry
    )

    # Load calendar to verify it exists
    calendar_with_metadata = repository.load_calendar(calendar_name, format)
    if calendar_with_metadata is None:
        logger.error(f"Calendar '{calendar_name}' not found")
        sys.exit(1)

    # Get latest filepath
    latest_path = repository.get_calendar_path(calendar_name, format)
    if latest_path is None:
        logger.error(f"No calendar file found for '{calendar_name}'")
        sys.exit(1)

    # Check if remote is configured
    if not config.calendar_git_remote_url and not git_service.get_remote_url():
        print("Warning: No remote URL configured. Calendar will be committed locally but not pushed.")
        print("Run 'calendar-sync git-setup' to configure a remote repository.")
    
    git_service.publish_calendar(calendar_name, latest_path, format)
