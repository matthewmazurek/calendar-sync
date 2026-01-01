"""Delete a calendar."""

from app.config import CalendarConfig
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage

from cli.utils import log_error


def delete_command(name: str) -> None:
    """Delete a calendar."""
    config = CalendarConfig.from_env()
    storage = CalendarStorage(config)
    repository = CalendarRepository(config.calendar_dir, storage)

    # Check if calendar directory exists (gracefully handle missing calendar file)
    calendar_dir = repository._get_calendar_dir(name)
    if not calendar_dir.exists():
        log_error(f"Calendar '{name}' not found")

    repository.delete_calendar(name)
    print(f"Calendar '{name}' deleted")
