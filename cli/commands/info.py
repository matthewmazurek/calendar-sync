"""Display calendar info and event count."""

import logging
import sys

from app.config import CalendarConfig
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage

logger = logging.getLogger(__name__)


def info_command(name: str) -> None:
    """Display calendar info and event count."""
    config = CalendarConfig.from_env()
    storage = CalendarStorage(config)
    repository = CalendarRepository(config.calendar_dir, storage)

    calendar_with_metadata = repository.load_calendar(name)
    if calendar_with_metadata is None:
        logger.error(f"Calendar '{name}' not found")
        sys.exit(1)

    calendar = calendar_with_metadata.calendar
    metadata = calendar_with_metadata.metadata

    print(f"Calendar: {name}")
    print(f"  Events: {len(calendar.events)}")
    print(f"  Format: {metadata.format}")

    # Calculate date range from events
    if calendar.events:
        dates = [event.date for event in calendar.events]
        min_date = min(dates)
        max_date = max(dates)
        print(f"  Date range: {min_date} to {max_date}")
    else:
        print(f"  Date range: no events")

    # Show source revised date from metadata
    if metadata.source_revised_at:
        print(f"  Source revised at: {metadata.source_revised_at}")

    print(f"  Created: {metadata.created}")
    print(f"  Last updated: {metadata.last_updated}")
    print(f"  Revision count: {metadata.revision_count}")
