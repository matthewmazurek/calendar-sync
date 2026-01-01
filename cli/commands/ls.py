"""List calendars or versions."""

from app.config import CalendarConfig
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage
from app.storage.git_service import GitService
from cli.setup import setup_reader_registry
from cli.utils import format_file_size, format_relative_time


def ls_command(
    name: str | None = None,
    include_archived: bool = False,
    show_info: bool = False,
    limit: int | None = None,
    show_all: bool = False,
) -> None:
    """
    List calendars or versions.

    If name is provided, list versions for that calendar.
    Otherwise, list all calendars.

    Args:
        name: Calendar name (optional)
        include_archived: If True, include archived calendars in the list
        show_info: If True, show detailed information (file path, size, event count)
        limit: Limit number of versions to show (None = use config default)
        show_all: If True, show all versions (overrides limit)
    """
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

    if name is None:
        # List all calendars
        calendars = repository.list_calendars(include_deleted=include_archived)
        if not calendars:
            print("No calendars found")
            return

        # Count archived calendars (archived calendars not shown)
        if not include_archived:
            all_calendars = repository.list_calendars(include_deleted=True)
            visible_calendars = repository.list_calendars(include_deleted=False)
            archived_count = len(all_calendars) - len(visible_calendars)
        else:
            archived_count = 0

        print(
            f"Listing calendars at {config.calendar_dir} ({archived_count} archived):"
        )
        for cal_name in calendars:
            # Check if calendar directory exists
            calendar_dir = repository._get_calendar_dir(cal_name)
            archived_marker = " (archived)" if not calendar_dir.exists() else ""
            if show_info:
                # Show directory path
                dir_path = str(calendar_dir)
                print(f"  {cal_name}  ({dir_path}){archived_marker}")
            else:
                print(f"  {cal_name}{archived_marker}")
    else:
        # List versions for specific calendar
        all_versions = repository.list_calendar_versions(name)
        if not all_versions:
            print(f"No versions found for calendar '{name}'")
            return

        # Apply pagination
        total_versions = len(all_versions)
        truncated = False
        if not show_all:
            if limit is None:
                limit = config.ls_default_limit
            if limit and total_versions > limit:
                versions = all_versions[:limit]
                truncated = True
            else:
                versions = all_versions
        else:
            versions = all_versions

        # Get calendar directory path for display
        calendar_dir = repository._get_calendar_dir(name)
        dir_path = str(calendar_dir)

        # Determine calendar file path (check both formats)
        git_service = repository.git_service
        repo_root = git_service.repo_root
        calendar_path = None
        for fmt in ["ics", "json"]:
            path = repository.get_calendar_path(name, format=fmt)
            if path and path.exists():
                calendar_path = path
                break

        # If no existing file found, default to ics format for path display
        if calendar_path is None:
            calendar_path = repository._get_calendar_file_path(name, format="ics")

        # Get relative path from repo root for header display
        try:
            rel_path = calendar_path.relative_to(repo_root)
            file_path_str = str(rel_path)
        except ValueError:
            file_path_str = str(calendar_path)

        print(
            f"Versions for calendar '{name}' ({file_path_str}) ({total_versions} total):"
        )
        print()

        # Find which commit the current file matches
        current_commit_hash = None
        try:
            # Use the calendar_path we already determined, but check if it exists
            if calendar_path and calendar_path.exists():
                current_commit_hash = repository.git_service.get_current_commit_hash(
                    calendar_path
                )
        except Exception:
            pass

        # calendar_path already determined above for header display

        # Print table header
        if show_info:
            print(
                f"{'#':>4}  {'HASH':<8}  {'DATE':<19}  {'TIME':<8}  {'SIZE':<8}  {'EVENTS':>6}  {'PATH'}"
            )
        else:
            print(f"{'#':>4}  {'HASH':<8}  {'DATE':<19}  {'TIME':<8}")

        for idx, (commit_hash, commit_date, commit_message) in enumerate(versions, 1):
            short_hash = commit_hash[:7]
            relative_time = format_relative_time(commit_date)

            # Format actual date/time
            if commit_date.tzinfo is None:
                from datetime import timezone

                commit_date = commit_date.replace(tzinfo=timezone.utc)
            date_str = commit_date.strftime("%Y-%m-%d %H:%M:%S")
            time_str = relative_time

            # Get detailed info if --info flag is set
            file_path_str = ""
            file_size_str = ""
            event_count = None

            if show_info:
                try:
                    # Get relative path from repo root
                    try:
                        rel_path = calendar_path.relative_to(repo_root)
                        file_path_str = str(rel_path)
                    except ValueError:
                        file_path_str = str(calendar_path)

                    # Get file content to calculate size and event count
                    calendar_content = git_service.get_file_at_commit(
                        calendar_path, commit_hash
                    )
                    if calendar_content:
                        file_size = len(calendar_content)
                        file_size_str = format_file_size(file_size)

                        # Try to count VEVENT components in ICS file
                        if calendar_path.suffix == ".ics":
                            event_count = calendar_content.decode("utf-8").count(
                                "BEGIN:VEVENT"
                            )
                except Exception:
                    pass

            # Format output with columns
            version_num = idx
            current_marker = " ← current" if commit_hash == current_commit_hash else ""

            if show_info:
                # Detailed output with file path and size
                event_count_str = str(event_count) if event_count is not None else "-"
                print(
                    f"{version_num:>4}  {short_hash:<8}  {date_str:<19}  {time_str:<8}  {file_size_str:<8}  {event_count_str:>6}  {file_path_str}{current_marker}"
                )
            else:
                # Standard output (no event count for efficiency)
                print(
                    f"{version_num:>4}  {short_hash:<8}  {date_str:<19}  {time_str:<8}{current_marker}"
                )

        # Show truncation message if applicable
        if truncated:
            print()
            print(
                f"... (showing {len(versions)} of {total_versions} versions, use --all to see all)"
            )
