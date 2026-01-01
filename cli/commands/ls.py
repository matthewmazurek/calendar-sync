"""List calendars or versions."""

from app.config import CalendarConfig
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage

from cli.utils import format_relative_time


def ls_command(name: str | None = None, include_deleted: bool = False) -> None:
    """
    List calendars or versions.

    If name is provided, list versions for that calendar.
    Otherwise, list all calendars.

    Args:
        name: Calendar name (optional)
        include_deleted: If True, include deleted calendars in the list
    """
    config = CalendarConfig.from_env()
    storage = CalendarStorage(config)
    repository = CalendarRepository(config.calendar_dir, storage)

    if name is None:
        # List all calendars
        calendars = repository.list_calendars(include_deleted=include_deleted)
        if not calendars:
            print("No calendars found")
            return

        print("Available calendars:")
        for cal_name in calendars:
            # Check if calendar directory exists
            calendar_dir = repository._get_calendar_dir(cal_name)
            deleted_marker = " (deleted)" if not calendar_dir.exists() else ""
            print(f"  {cal_name}{deleted_marker}")
    else:
        # List versions for specific calendar
        versions = repository.list_calendar_versions(name)
        if not versions:
            print(f"No versions found for calendar '{name}'")
            return

        print(f"Versions for calendar '{name}' ({len(versions)} total):")
        print()

        # Find which commit the current file matches
        current_commit_hash = None
        try:
            calendar_path = repository.get_latest_calendar_path(name)
            if calendar_path and calendar_path.exists():
                git_service = repository.git_service
                current_file_content = calendar_path.read_bytes()
                
                # Check if file matches HEAD first (most common case)
                if git_service.file_matches_head(calendar_path) and versions:
                    current_commit_hash = versions[0][0]  # First commit is latest
                else:
                    # File doesn't match HEAD, check which commit it matches
                    # Start from newest and work backwards
                    for commit_hash, _, _ in versions:
                        commit_content = git_service.get_file_at_commit(calendar_path, commit_hash)
                        if commit_content and commit_content == current_file_content:
                            current_commit_hash = commit_hash
                            break
        except Exception:
            pass

        for idx, (commit_hash, commit_date, commit_message) in enumerate(versions, 1):
            short_hash = commit_hash[:7]
            relative_time = format_relative_time(commit_date)
            
            # Format actual date/time
            if commit_date.tzinfo is None:
                from datetime import timezone
                commit_date = commit_date.replace(tzinfo=timezone.utc)
            actual_time = commit_date.strftime("%Y-%m-%d %H:%M")
            time_str = f"{relative_time} ({actual_time})"

            # Try to get event count from calendar file at this commit
            event_count = None
            try:
                git_service = repository.git_service
                # Use the calendar path even if it doesn't exist in working directory
                # Default to 'ics' format for version listing
                calendar_path = repository._get_calendar_file_path(name, format="ics")
                calendar_content = git_service.get_file_at_commit(calendar_path, commit_hash)
                if calendar_content:
                    # Try to count VEVENT components in ICS file
                    if calendar_path.suffix == '.ics':
                        event_count = calendar_content.decode('utf-8').count('BEGIN:VEVENT')
            except Exception:
                # If we can't get event count, just continue without it
                pass

            # Format output with columns
            version_num = f"#{idx}"
            hash_str = short_hash
            count_info = f"({event_count} events)" if event_count is not None else ""
            current_marker = " ← current" if commit_hash == current_commit_hash else ""

            # Build the line - align columns nicely
            print(f"  {version_num:>4}  {hash_str:8}  {time_str:35}  {count_info}{current_marker}")
