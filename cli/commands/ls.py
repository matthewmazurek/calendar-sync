"""List calendars or versions."""

from pathlib import Path

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


def _list_calendars(
    repository, config, renderer: TableRenderer, include_archived: bool
) -> None:
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
    for cal_id in calendars:
        paths = repository.paths(cal_id)
        archived = not paths.directory.exists()

        # Get config file path (relative to cwd for terminal links)
        if paths.settings.exists():
            try:
                config_display = str(paths.settings.resolve().relative_to(Path.cwd()))
            except ValueError:
                config_display = str(paths.settings.resolve())
        else:
            config_display = "-"

        # Get last updated from calendar
        last_updated = None
        calendar = repository.load_calendar(cal_id)
        if calendar:
            last_updated = calendar.last_updated

        # Get display name and created date from settings
        settings = repository.load_settings(cal_id)
        display_name = settings.name if settings else None
        created = settings.created if settings else None

        calendar_info.append(
            CalendarInfo(
                id=cal_id,
                archived=archived,
                config_path=config_display,
                last_updated=last_updated,
                name=display_name,
                created=created,
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

    # Get paths for this calendar
    paths = repository.paths(name)
    git_service = repository.git_service
    repo_root = git_service.repo_root

    # ICS export path for display (what users subscribe to)
    calendar_path = paths.export("ics")

    # Canonical path for version tracking (data.json is the source of truth)
    canonical_path = paths.data

    # Find which commit the current canonical file matches
    current_commit_hash = None
    try:
        if canonical_path.exists():
            current_commit_hash = repository.git_service.get_current_commit_hash(
                canonical_path
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
