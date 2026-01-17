"""Table renderer for calendar and version lists."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rich.table import Table

from cli.display.console import console
from cli.display.formatters import format_file_size, format_relative_time


@dataclass
class CalendarInfo:
    """Information about a calendar for display."""

    name: str
    archived: bool
    path: str
    last_updated: datetime | None


@dataclass
class VersionInfo:
    """Information about a calendar version for display."""

    version_num: int
    commit_hash: str
    commit_date: datetime
    is_current: bool
    file_size: int | None = None
    event_count: int | None = None
    file_path: str | None = None


class TableRenderer:
    """Render tables for calendar and version lists.

    Uses Rich's Table class for consistent, well-formatted output.
    """

    def render_calendar_list(
        self,
        calendars: list[CalendarInfo],
        calendar_dir: Path,
        archived_count: int = 0,
    ) -> None:
        """Render a list of calendars as a table.

        Args:
            calendars: List of CalendarInfo objects to display.
            calendar_dir: Base directory where calendars are stored.
            archived_count: Number of archived calendars (for header).
        """
        if not calendars:
            console.print("No calendars found")
            return

        console.print(
            f"Listing calendars at {calendar_dir.resolve()} ({archived_count} archived):"
        )
        console.print()

        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("NAME", style="cyan")
        table.add_column("DATE", style="dim")
        table.add_column("UPDATED", style="dim")
        table.add_column("PATH", style="dim")

        for cal in calendars:
            name_display = cal.name
            if cal.archived:
                name_display += " [dim](archived)[/dim]"

            if cal.last_updated:
                date_str = cal.last_updated.strftime("%Y-%m-%d")
                updated_str = format_relative_time(cal.last_updated)
            else:
                date_str = "-"
                updated_str = "-"

            table.add_row(name_display, date_str, updated_str, cal.path)

        console.print(table)

    def render_version_list(
        self,
        versions: list[VersionInfo],
        calendar_name: str,
        calendar_path: Path,
        total_versions: int,
        show_details: bool = False,
        truncated: bool = False,
    ) -> None:
        """Render a list of calendar versions as a table.

        Args:
            versions: List of VersionInfo objects to display.
            calendar_name: Name of the calendar.
            calendar_path: Path to the calendar file.
            total_versions: Total number of versions (for header).
            show_details: Whether to show detailed info (size, events, path).
            truncated: Whether the list was truncated.
        """
        if not versions:
            console.print(f"No versions found for calendar '{calendar_name}'")
            return

        console.print(
            f"Versions for calendar '{calendar_name}' ({calendar_path.resolve()}) ({total_versions} total):"
        )
        console.print()

        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("#", justify="right", style="dim")
        table.add_column("HASH", style="cyan")
        table.add_column("DATE")
        table.add_column("UPDATED", style="dim")

        if show_details:
            table.add_column("SIZE", justify="right", style="dim")
            table.add_column("EVENTS", justify="right")
            table.add_column("PATH", style="dim")

        for ver in versions:
            short_hash = ver.commit_hash[:7]

            # Format date/time
            commit_date = ver.commit_date
            if commit_date.tzinfo is None:
                commit_date = commit_date.replace(tzinfo=timezone.utc)
            date_str = commit_date.strftime("%Y-%m-%d %H:%M:%S")
            relative_str = format_relative_time(commit_date)

            # Current marker
            current_marker = " [green]← current[/green]" if ver.is_current else ""

            if show_details:
                size_str = format_file_size(ver.file_size) if ver.file_size else "-"
                events_str = str(ver.event_count) if ver.event_count is not None else "-"
                path_str = (ver.file_path or "") + current_marker

                table.add_row(
                    str(ver.version_num),
                    short_hash,
                    date_str,
                    relative_str,
                    size_str,
                    events_str,
                    path_str,
                )
            else:
                table.add_row(
                    str(ver.version_num),
                    short_hash,
                    date_str,
                    relative_str + current_marker,
                )

        console.print(table)

        if truncated:
            console.print()
            console.print(
                f"[dim]... (showing {len(versions)} of {total_versions} versions, use --all to see all)[/dim]"
            )

    def render_empty(self, message: str) -> None:
        """Render an empty state message.

        Args:
            message: Message to display.
        """
        console.print(f"[dim]{message}[/dim]")
