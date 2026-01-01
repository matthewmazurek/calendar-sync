"""Restore calendar to specific git commit."""

from app.config import CalendarConfig
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage
from cli.utils import log_error


def restore_command(name: str, commit: str) -> None:
    """Restore calendar to specific git commit."""
    config = CalendarConfig.from_env()
    storage = CalendarStorage(config)
    repository = CalendarRepository(config.calendar_dir, storage)

    # Check if calendar has any versions in git history (works for deleted calendars too)
    versions = repository.list_calendar_versions(name)
    if not versions:
        log_error(f"Calendar '{name}' not found in git history")

    # Get calendar directory (even if it doesn't exist yet)
    calendar_dir = repository._get_calendar_dir(name)

    # Ensure calendar directory exists (for deleted calendars)
    calendar_dir.mkdir(parents=True, exist_ok=True)

    # Restore entire directory from git (includes calendar.ics, metadata.json, etc.)
    git_service = repository.git_service
    if git_service.restore_directory_version(calendar_dir, commit):
        print(f"Calendar '{name}' restored to commit {commit[:7]}")
    else:
        log_error(f"Failed to restore calendar '{name}' to commit {commit}")
