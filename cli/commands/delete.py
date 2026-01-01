"""Delete a calendar."""

import logging
import sys

from app.config import CalendarConfig
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage

logger = logging.getLogger(__name__)


def delete_command(name: str, purge_history: bool = False) -> None:
    """
    Delete a calendar.

    Args:
        name: Calendar name to delete
        purge_history: If True, remove from git history entirely (hard delete)
    """
    config = CalendarConfig.from_env()
    storage = CalendarStorage(config)
    repository = CalendarRepository(config.calendar_dir, storage)

    calendar_dir = repository._get_calendar_dir(name)
    calendar_exists = calendar_dir.exists()

    if purge_history:
        # Hard delete: remove from git history entirely
        # This works even if calendar was already deleted from filesystem
        print(f"Purging calendar '{name}' from git history (this will rewrite history)...")
        if repository.git_publisher.purge_from_history(name):
            # After purging from history, remove from filesystem if it still exists
            if calendar_exists:
                repository.delete_calendar(name)
            print(f"Calendar '{name}' purged from git history")
        else:
            logger.error(f"Failed to purge calendar '{name}' from git history")
            sys.exit(1)
    else:
        # Regular delete: requires calendar to exist
        if not calendar_exists:
            logger.error(f"Calendar '{name}' not found")
            sys.exit(1)

        # Remove from filesystem and commit deletion to git
        repository.delete_calendar(name)
        # Commit the deletion to git for audit trail
        repository.git_publisher.commit_deletion(name)
        print(f"Calendar '{name}' deleted")
