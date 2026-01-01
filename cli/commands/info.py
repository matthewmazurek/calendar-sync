"""Display calendar info and event count."""

import logging
import sys
from datetime import date, datetime, timezone

from app.config import CalendarConfig
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage
from cli.utils import format_relative_time

logger = logging.getLogger(__name__)


def _format_datetime(dt, include_relative=True):
    """Format datetime or date with optional relative time."""
    if dt is None:
        return "N/A"

    # Handle date objects (no time component)
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")

    # Handle datetime objects
    # Ensure timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    if include_relative:
        relative = format_relative_time(dt)
        return f"{date_str} ({relative})"
    return date_str


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

    # Get calendar path
    calendar_path = repository.get_calendar_path(name, metadata.format)

    # Header
    print(f"Calendar: {name} ({calendar_path})")
    print()

    # Basic info
    label_width = 18
    print(f"{'Events:':<{label_width}} {len(calendar.events):,}")
    print(f"{'Format:':<{label_width}} {metadata.format}")

    # Calculate date range from events
    if calendar.events:
        dates = [event.date for event in calendar.events]
        min_date = min(dates)
        max_date = max(dates)
        print(f"{'Date range:':<{label_width}} {min_date} to {max_date}")
    else:
        print(f"{'Date range:':<{label_width}} no events")

    print()

    # Timestamps
    if metadata.source_revised_at:
        print(
            f"{'Source revised:':<{label_width}} {_format_datetime(metadata.source_revised_at)}"
        )
    print(f"{'Created:':<{label_width}} {_format_datetime(metadata.created)}")
    print(f"{'Last updated:':<{label_width}} {_format_datetime(metadata.last_updated)}")

    # Get git commit history to show actual commit count
    versions = repository.list_calendar_versions(name, metadata.format)
    commit_count = len(versions)

    if commit_count > 0:
        print()
        print(f"{'Git commits:':<{label_width}} {commit_count}")

        # Get latest commit info
        latest_commit_hash, latest_commit_date, latest_commit_message = versions[0]

        # Get current version (what's in working directory)
        calendar_path = repository.get_calendar_path(name, metadata.format)
        current_commit_hash = None
        if calendar_path:
            current_commit_hash = repository.git_service.get_current_commit_hash(
                calendar_path
            )

        # Show current version
        if current_commit_hash:
            # Find the commit date for current version
            current_commit_date = None
            for commit_hash, commit_date, _ in versions:
                if commit_hash == current_commit_hash:
                    current_commit_date = commit_date
                    break

            if current_commit_date:
                current_str = (
                    f"{current_commit_hash[:7]} {_format_datetime(current_commit_date)}"
                )
            else:
                current_str = current_commit_hash[:7]
        else:
            current_str = "uncommitted changes"

        print(f"{'Current version:':<{label_width}} {current_str}")
        print(
            f"{'Latest commit:':<{label_width}} {latest_commit_hash[:7]} {_format_datetime(latest_commit_date)}"
        )
    else:
        print()
        print(f"{'Git commits:':<{label_width}} N/A (not in git repository)")
