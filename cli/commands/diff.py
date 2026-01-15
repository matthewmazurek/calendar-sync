"""Compare calendar versions."""

import logging
from datetime import timezone
from typing import Any

import typer
from typing_extensions import Annotated

from app.models.calendar import Calendar
from cli.context import get_context

logger = logging.getLogger(__name__)


def _resolve_version(
    commit: str,
    versions: list[tuple[str, Any, str]],
) -> tuple[str | None, str]:
    """
    Resolve a version specifier to a commit hash.

    Args:
        commit: Version specifier (#N, N, latest, previous, HEAD, working, or commit hash)
        versions: List of (commit_hash, commit_date, commit_message) tuples

    Returns:
        Tuple of (commit_hash or None for working, display_name)
        Returns (None, "working") for working directory version
    """
    commit_lower = commit.lower()

    # Special case: working directory (current unsaved state)
    if commit_lower in ("working", "work", "current", "local"):
        return None, "working"

    # Special case: HEAD (latest committed version)
    if commit_lower == "head":
        if not versions:
            return None, "working"
        return versions[0][0], f"HEAD ({versions[0][0][:7]})"

    # Check for version number (#3 or 3)
    if commit.startswith("#"):
        try:
            version_num = int(commit[1:])
            if 1 <= version_num <= len(versions):
                target = versions[version_num - 1][0]
                return target, f"#{version_num} ({target[:7]})"
        except ValueError:
            pass
    elif commit.isdigit():
        try:
            version_num = int(commit)
            if 1 <= version_num <= len(versions):
                target = versions[version_num - 1][0]
                return target, f"#{version_num} ({target[:7]})"
        except ValueError:
            pass

    # Relative commands
    if commit_lower == "latest":
        if versions:
            target = versions[0][0]
            return target, f"latest ({target[:7]})"
        return None, "working"
    elif commit_lower == "previous":
        if len(versions) >= 2:
            target = versions[1][0]
            return target, f"previous ({target[:7]})"
        raise typer.BadParameter(f"Only {len(versions)} version(s) available")

    # Treat as commit hash - find matching commit
    for v_hash, _, _ in versions:
        if v_hash.startswith(commit):
            return v_hash, v_hash[:7]

    raise typer.BadParameter(f"Version '{commit}' not found")


def _get_calendar_at_version(
    repository, name: str, commit: str | None, format: str = "ics"
) -> Calendar | None:
    """
    Load calendar at a specific version.

    Args:
        repository: CalendarRepository instance
        name: Calendar name
        commit: Commit hash, or None for working directory
        format: Calendar format

    Returns:
        Calendar object or None
    """
    if commit is None:
        # Load working directory version
        result = repository.load_calendar(name, format)
        return result.calendar if result else None
    else:
        # Load from git commit
        result = repository.load_calendar_by_commit(name, commit, format)
        return result.calendar if result else None


def _format_event_summary(event) -> str:
    """Format an event for display."""
    date_str = event.date.strftime("%Y-%m-%d")
    time_str = ""
    if event.start:
        time_str = f" {event.start.strftime('%H:%M')}"
        if event.end:
            time_str += f"-{event.end.strftime('%H:%M')}"
    return f"{date_str}{time_str}: {event.title}"


def _compute_diff(
    old_calendar: Calendar | None,
    new_calendar: Calendar | None,
) -> tuple[list, list, list]:
    """
    Compute differences between two calendars.

    Returns:
        Tuple of (added_events, removed_events, modified_events)
        modified_events is a list of (old_event, new_event) tuples
    """
    if old_calendar is None:
        old_events = []
    else:
        old_events = old_calendar.events

    if new_calendar is None:
        new_events = []
    else:
        new_events = new_calendar.events

    # Create lookup by (date, title, start, end) as the primary key
    def event_key(e):
        return (e.date, e.title, e.start, e.end)

    # Secondary key for detecting modifications (date + title only)
    def event_identity(e):
        return (e.date, e.title)

    old_by_key = {event_key(e): e for e in old_events}
    new_by_key = {event_key(e): e for e in new_events}

    old_by_identity = {}
    for e in old_events:
        identity = event_identity(e)
        if identity not in old_by_identity:
            old_by_identity[identity] = []
        old_by_identity[identity].append(e)

    new_by_identity = {}
    for e in new_events:
        identity = event_identity(e)
        if identity not in new_by_identity:
            new_by_identity[identity] = []
        new_by_identity[identity].append(e)

    added = []
    removed = []
    modified = []
    processed_old = set()
    processed_new = set()

    # FIRST PASS: Process exact matches first to avoid greedy modification matching
    for event in new_events:
        key = event_key(event)
        if key in old_by_key:
            # Exact match - no change
            processed_old.add(key)
            processed_new.add(key)

    # SECOND PASS: Find added and modified events (only for unprocessed new events)
    for event in new_events:
        key = event_key(event)
        if key in processed_new:
            # Already handled as exact match
            continue

        # Check if there's a similar event (same date and title) that was modified
        identity = event_identity(event)
        if identity in old_by_identity:
            # Find first unprocessed old event with same identity
            old_matches = old_by_identity[identity]
            found_match = False
            for old_event in old_matches:
                old_key = event_key(old_event)
                if old_key not in processed_old:
                    # Found a modification
                    if _events_differ(old_event, event):
                        modified.append((old_event, event))
                    processed_old.add(old_key)
                    processed_new.add(key)
                    found_match = True
                    break
            if not found_match:
                added.append(event)
        else:
            # Truly new event
            added.append(event)

    # Find removed events (in old but not processed)
    for event in old_events:
        key = event_key(event)
        if key not in processed_old and key not in new_by_key:
            removed.append(event)

    return added, removed, modified


def _events_differ(old, new) -> bool:
    """Check if two events differ in meaningful ways."""
    if old.title != new.title:
        return True
    if old.date != new.date:
        return True
    if old.start != new.start:
        return True
    if old.end != new.end:
        return True
    if old.location != new.location:
        return True
    return False


def diff(
    name: Annotated[
        str,
        typer.Argument(help="Calendar name"),
    ],
    version1: Annotated[
        str,
        typer.Argument(
            help="First version: commit hash, #N, N, latest, previous, HEAD, or working"
        ),
    ] = "previous",
    version2: Annotated[
        str,
        typer.Argument(
            help="Second version: commit hash, #N, N, latest, previous, HEAD, or working"
        ),
    ] = "working",
    compact: Annotated[
        bool,
        typer.Option("--compact", "-c", help="Show compact output (counts only)"),
    ] = False,
    stats: Annotated[
        bool,
        typer.Option("--stats", "-s", help="Show statistics summary"),
    ] = False,
) -> None:
    """
    Compare two versions of a calendar.

    By default, compares the previous committed version with the current working directory.

    Version specifiers:
      - working/current: Current working directory (uncommitted)
      - HEAD/latest: Most recent committed version
      - previous: Second most recent committed version
      - #N or N: Specific version number (1 = latest)
      - <hash>: Git commit hash (full or partial)

    Examples:
      diff mazurek                    # Compare previous vs working
      diff mazurek HEAD working       # Compare latest commit vs working
      diff mazurek #1 #2              # Compare version 1 vs version 2
      diff mazurek abc123 def456      # Compare two specific commits
    """
    ctx = get_context()
    repository = ctx.repository

    # Get version history
    versions = repository.list_calendar_versions(name)
    if not versions:
        # Check if calendar exists at all
        calendar = repository.load_calendar(name)
        if calendar is None:
            logger.error(f"Calendar '{name}' not found")
            raise typer.Exit(1)
        # Calendar exists but has no git history
        typer.echo(f"Calendar '{name}' has no version history.")
        raise typer.Exit(0)

    # Resolve version specifiers
    try:
        commit1, display1 = _resolve_version(version1, versions)
        commit2, display2 = _resolve_version(version2, versions)
    except typer.BadParameter as e:
        logger.error(str(e))
        raise typer.Exit(1)

    # Warn if comparing same version
    if commit1 == commit2:
        typer.echo(f"Comparing {display1} with itself - no differences.")
        raise typer.Exit(0)

    # Load calendars at each version
    cal1 = _get_calendar_at_version(repository, name, commit1)
    cal2 = _get_calendar_at_version(repository, name, commit2)

    if cal1 is None and cal2 is None:
        logger.error(f"Could not load calendar '{name}' at either version")
        raise typer.Exit(1)

    # Compute differences
    added, removed, modified = _compute_diff(cal1, cal2)

    # Header
    typer.echo(f"Comparing calendar '{name}':")
    typer.echo(f"  {display1} → {display2}")
    typer.echo()

    # Show counts
    total_changes = len(added) + len(removed) + len(modified)
    if total_changes == 0:
        typer.echo("No differences found.")
        raise typer.Exit(0)

    # Stats mode or compact mode
    if compact or stats:
        typer.echo(f"  Added:    {len(added):>4} event(s)")
        typer.echo(f"  Removed:  {len(removed):>4} event(s)")
        typer.echo(f"  Modified: {len(modified):>4} event(s)")
        typer.echo(f"  ─────────────────")
        typer.echo(f"  Total:    {total_changes:>4} change(s)")

        if compact:
            raise typer.Exit(0)

        typer.echo()

    # Detailed output
    if added:
        typer.echo(typer.style("Added events:", fg=typer.colors.GREEN, bold=True))
        for event in sorted(added, key=lambda e: (e.date, e.start or e.date)):
            typer.echo(
                typer.style(
                    f"  + {_format_event_summary(event)}", fg=typer.colors.GREEN
                )
            )
        typer.echo()

    if removed:
        typer.echo(typer.style("Removed events:", fg=typer.colors.RED, bold=True))
        for event in sorted(removed, key=lambda e: (e.date, e.start or e.date)):
            typer.echo(
                typer.style(f"  - {_format_event_summary(event)}", fg=typer.colors.RED)
            )
        typer.echo()

    if modified:
        typer.echo(typer.style("Modified events:", fg=typer.colors.YELLOW, bold=True))
        for old_event, new_event in sorted(
            modified, key=lambda x: (x[1].date, x[1].start or x[1].date)
        ):
            typer.echo(
                typer.style(
                    f"  ~ {_format_event_summary(new_event)}", fg=typer.colors.YELLOW
                )
            )
            # Show what changed
            if old_event.title != new_event.title:
                typer.echo(f"      title: {old_event.title} → {new_event.title}")
            if old_event.date != new_event.date:
                typer.echo(f"      date: {old_event.date} → {new_event.date}")
            if old_event.start != new_event.start:
                old_time = (
                    old_event.start.strftime("%H:%M") if old_event.start else "none"
                )
                new_time = (
                    new_event.start.strftime("%H:%M") if new_event.start else "none"
                )
                typer.echo(f"      start: {old_time} → {new_time}")
            if old_event.end != new_event.end:
                old_time = old_event.end.strftime("%H:%M") if old_event.end else "none"
                new_time = new_event.end.strftime("%H:%M") if new_event.end else "none"
                typer.echo(f"      end: {old_time} → {new_time}")
            if old_event.location != new_event.location:
                typer.echo(
                    f"      location: {old_event.location or 'none'} → {new_event.location or 'none'}"
                )
        typer.echo()

    # Summary line
    if not stats:
        summary_parts = []
        if added:
            summary_parts.append(typer.style(f"+{len(added)}", fg=typer.colors.GREEN))
        if removed:
            summary_parts.append(typer.style(f"-{len(removed)}", fg=typer.colors.RED))
        if modified:
            summary_parts.append(
                typer.style(f"~{len(modified)}", fg=typer.colors.YELLOW)
            )
        typer.echo(f"Summary: {', '.join(summary_parts)}")


def display_diff(
    old_calendar: Calendar | None,
    new_calendar: Calendar | None,
    old_label: str = "before",
    new_label: str = "after",
    compact: bool = False,
) -> bool:
    """
    Display differences between two calendars.

    Args:
        old_calendar: Calendar before changes (or None)
        new_calendar: Calendar after changes (or None)
        old_label: Label for the old version
        new_label: Label for the new version
        compact: If True, only show counts

    Returns:
        True if there were differences, False otherwise
    """
    # Compute differences
    added, removed, modified = _compute_diff(old_calendar, new_calendar)

    # Check if there are changes
    total_changes = len(added) + len(removed) + len(modified)
    if total_changes == 0:
        typer.echo("No differences.")
        return False

    # Header
    typer.echo(f"\nChanges ({old_label} → {new_label}):")
    typer.echo()

    # Compact mode - counts only
    if compact:
        typer.echo(f"  Added:    {len(added):>4} event(s)")
        typer.echo(f"  Removed:  {len(removed):>4} event(s)")
        typer.echo(f"  Modified: {len(modified):>4} event(s)")
        typer.echo(f"  ─────────────────")
        typer.echo(f"  Total:    {total_changes:>4} change(s)")
        return True

    # Detailed output
    if added:
        typer.echo(typer.style("Added events:", fg=typer.colors.GREEN, bold=True))
        for event in sorted(added, key=lambda e: (e.date, e.start or e.date)):
            typer.echo(
                typer.style(
                    f"  + {_format_event_summary(event)}", fg=typer.colors.GREEN
                )
            )
        typer.echo()

    if removed:
        typer.echo(typer.style("Removed events:", fg=typer.colors.RED, bold=True))
        for event in sorted(removed, key=lambda e: (e.date, e.start or e.date)):
            typer.echo(
                typer.style(f"  - {_format_event_summary(event)}", fg=typer.colors.RED)
            )
        typer.echo()

    if modified:
        typer.echo(typer.style("Modified events:", fg=typer.colors.YELLOW, bold=True))
        for old_event, new_event in sorted(
            modified, key=lambda x: (x[1].date, x[1].start or x[1].date)
        ):
            typer.echo(
                typer.style(
                    f"  ~ {_format_event_summary(new_event)}", fg=typer.colors.YELLOW
                )
            )
            # Show what changed
            if old_event.title != new_event.title:
                typer.echo(f"      title: {old_event.title} → {new_event.title}")
            if old_event.date != new_event.date:
                typer.echo(f"      date: {old_event.date} → {new_event.date}")
            if old_event.start != new_event.start:
                old_time = (
                    old_event.start.strftime("%H:%M") if old_event.start else "none"
                )
                new_time = (
                    new_event.start.strftime("%H:%M") if new_event.start else "none"
                )
                typer.echo(f"      start: {old_time} → {new_time}")
            if old_event.end != new_event.end:
                old_time = old_event.end.strftime("%H:%M") if old_event.end else "none"
                new_time = new_event.end.strftime("%H:%M") if new_event.end else "none"
                typer.echo(f"      end: {old_time} → {new_time}")
            if old_event.location != new_event.location:
                typer.echo(
                    f"      location: {old_event.location or 'none'} → {new_event.location or 'none'}"
                )
        typer.echo()

    # Summary line
    summary_parts = []
    if added:
        summary_parts.append(typer.style(f"+{len(added)}", fg=typer.colors.GREEN))
    if removed:
        summary_parts.append(typer.style(f"-{len(removed)}", fg=typer.colors.RED))
    if modified:
        summary_parts.append(typer.style(f"~{len(modified)}", fg=typer.colors.YELLOW))
    typer.echo(f"Summary: {', '.join(summary_parts)}")

    return True
