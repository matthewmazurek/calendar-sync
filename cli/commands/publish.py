"""Publish an existing calendar to git."""

from app.config import CalendarConfig
from app.publish import GitPublisher
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage

from cli.utils import log_error


def publish_command(calendar_name: str, format: str = "ics") -> None:
    """Publish an existing calendar to git."""
    config = CalendarConfig.from_env()
    storage = CalendarStorage(config)
    repository = CalendarRepository(config.calendar_dir, storage)

    # Load calendar to verify it exists
    calendar_with_metadata = repository.load_calendar(calendar_name, format)
    if calendar_with_metadata is None:
        log_error(f"Calendar '{calendar_name}' not found")

    # Get latest filepath
    latest_path = repository.get_latest_calendar_path(calendar_name, format)
    if latest_path is None:
        log_error(f"No calendar file found for '{calendar_name}'")

    # Publish
    publisher = GitPublisher(config.calendar_dir)
    publisher.publish_calendar(calendar_name, latest_path, format)
