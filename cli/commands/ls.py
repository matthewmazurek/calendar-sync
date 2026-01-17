"""List calendars or versions."""

import typer
from typing_extensions import Annotated

from cli.context import get_context
from cli.display.table_renderer import CalendarInfo, TableRenderer, VersionInfo


def ls(
    name: Annotated[
        str | None,
        typer.Argument(
            help="Calendar name. If provided, lists versions for that calendar."
        ),
    ] = None,
    show_all: Annotated[
        bool,
        typer.Option("--all", "-a", help="Show all versions (overrides --limit)"),
    ] = False,
    include_archived: Annotated[
        bool,
        typer.Option("--archived", help="Include archived calendars"),
    ] = False,
    show_info: Annotated[
        bool,
        typer.Option(
            "--long",
            "-l",
            help="Show detailed information (file path, size, event count)",
        ),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-n", help="Limit number of versions to show"),
    ] = None,
) -> None:
    """List calendars or versions.

    If NAME is provided, lists versions for that calendar.
    Otherwise, lists all calendars.
    """
    ctx = get_context()
    config = ctx.config
    repository = ctx.repository
    renderer = TableRenderer()

    if name is None:
        _list_calendars(repository, config, renderer, include_archived)
    else:
        _list_versions(repository, config, renderer, name, show_all, show_info, limit)


def _list_calendars(repository, config, renderer: TableRenderer, include_archived: bool) -> None:
    """List all calendars."""
    calendars = repository.list_calendars(include_deleted=include_archived)
    if not calendars:
        renderer.render_empty("No calendars found")
        return

    # Count archived calendars
    if not include_archived:
        all_calendars = repository.list_calendars(include_deleted=True)
        visible_calendars = repository.list_calendars(include_deleted=False)
        archived_count = len(all_calendars) - len(visible_calendars)
    else:
        archived_count = 0

    # Collect calendar info
    calendar_info = []
    for cal_name in calendars:
        calendar_dir = repository._get_calendar_dir(cal_name)
        archived = not calendar_dir.exists()

        # Get calendar file path (check both formats)
        cal_path = None
        for fmt in ["ics", "json"]:
            path = repository.get_calendar_path(cal_name, format=fmt)
            if path and path.exists():
                cal_path = path
                break

        # Get last updated from metadata
        last_updated = None
        metadata = repository.load_metadata(cal_name)
        if metadata:
            last_updated = metadata.last_updated

        calendar_info.append(
            CalendarInfo(
                name=cal_name,
                archived=archived,
                path=str(cal_path) if cal_path else "-",
                last_updated=last_updated,
            )
        )

    renderer.render_calendar_list(calendar_info, config.calendar_dir, archived_count)


def _list_versions(
    repository,
    config,
    renderer: TableRenderer,
    name: str,
    show_all: bool,
    show_info: bool,
    limit: int | None,
) -> None:
    """List versions for a specific calendar."""
    all_versions = repository.list_calendar_versions(name)
    if not all_versions:
        renderer.render_empty(f"No versions found for calendar '{name}'")
        return

    # Apply pagination
    total_versions = len(all_versions)
    truncated = False
    if not show_all:
        if limit is None:
            limit = config.ls_default_limit
        if limit and total_versions > limit:
            versions_data = all_versions[:limit]
            truncated = True
        else:
            versions_data = all_versions
    else:
        versions_data = all_versions

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

    # Find which commit the current file matches
    current_commit_hash = None
    try:
        if calendar_path and calendar_path.exists():
            current_commit_hash = repository.git_service.get_current_commit_hash(
                calendar_path
            )
    except Exception:
        pass

    # Build version info objects
    versions = []
    for idx, (commit_hash, commit_date, commit_message) in enumerate(versions_data, 1):
        file_size = None
        event_count = None
        file_path_display = None

        if show_info:
            try:
                # Get relative path from repo root
                try:
                    rel_path = calendar_path.relative_to(repo_root)
                    file_path_display = str(rel_path)
                except ValueError:
                    file_path_display = str(calendar_path)

                # Get file content to calculate size and event count
                calendar_content = git_service.get_file_at_commit(
                    calendar_path, commit_hash
                )
                if calendar_content:
                    file_size = len(calendar_content)

                    # Try to count VEVENT components in ICS file
                    if calendar_path.suffix == ".ics":
                        event_count = calendar_content.decode("utf-8").count(
                            "BEGIN:VEVENT"
                        )
            except Exception:
                pass

        versions.append(
            VersionInfo(
                version_num=idx,
                commit_hash=commit_hash,
                commit_date=commit_date,
                is_current=commit_hash == current_commit_hash,
                file_size=file_size,
                event_count=event_count,
                file_path=file_path_display,
            )
        )

    renderer.render_version_list(
        versions,
        calendar_name=name,
        calendar_path=calendar_path,
        total_versions=total_versions,
        show_details=show_info,
        truncated=truncated,
    )
