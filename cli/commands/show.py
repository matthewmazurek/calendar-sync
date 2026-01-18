"""Display calendar events in agenda or list format."""

import logging
from datetime import date, datetime

import typer
from typing_extensions import Annotated

from app.calendar_query import CalendarQuery
from cli.context import get_context
from cli.display import RichEventRenderer
from cli.utils import require_calendar_with_data

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> date:
    """Parse a date string in YYYY-MM-DD format.

    Args:
        date_str: Date string to parse.

    Returns:
        Parsed date object.

    Raises:
        typer.BadParameter: If the date format is invalid.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise typer.BadParameter(f"Invalid date format: {date_str}. Use YYYY-MM-DD.")


def show(
    name: Annotated[
        str,
        typer.Argument(help="Calendar name"),
    ],
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Number of days to show"),
    ] = 7,
    target_date: Annotated[
        str | None,
        typer.Option("--date", help="Show events for specific date (YYYY-MM-DD)"),
    ] = None,
    year: Annotated[
        int | None,
        typer.Option("--year", "-y", help="Filter by year"),
    ] = None,
    view: Annotated[
        str,
        typer.Option("--view", "-v", help="View mode: 'agenda' or 'list'"),
    ] = "agenda",
    show_all: Annotated[
        bool,
        typer.Option("--all", "-a", help="Show all events (no date filter)"),
    ] = False,
) -> None:
    """Display calendar events.

    Shows events in either agenda view (grouped by day) or list view
    (flat list, useful for search results).

    Examples:
        calsync show <calendar>                # Next 7 days (agenda view)
        calsync show <calendar> --days 14      # Next 2 weeks
        calsync show <calendar> --date 2026-01-20   # Specific date
        calsync show <calendar> --year 2026    # All events in 2026
        calsync show <calendar> --all          # All events
        calsync show <calendar> --view list    # List format
    """
    ctx = get_context()
    repository = ctx.repository

    calendar = require_calendar_with_data(repository, name)
    query = CalendarQuery(calendar)
    renderer = RichEventRenderer()

    # Validate view mode
    if view not in ("agenda", "list"):
        logger.error(f"Invalid view mode: {view}. Use 'agenda' or 'list'.")
        raise typer.Exit(1)

    # Determine which events to show and build title/subtitle
    if target_date:
        # Specific date
        parsed_date = _parse_date(target_date)
        events = query.on_date(parsed_date)
        title = f"Events: {name}"
        subtitle = parsed_date.strftime("%a %b %d, %Y")
    elif year:
        # Specific year
        events = query.by_year(year)
        title = f"Events: {name}"
        subtitle = str(year)
    elif show_all:
        # All events
        events = query.all()
        title = f"Events: {name}"
        subtitle = "all"
    else:
        # Upcoming N days (default)
        events = query.upcoming(days=days)
        title = f"Upcoming: {name}"
        subtitle = f"{days} days" if days != 1 else "1 day"

    # Render based on view mode
    if view == "agenda":
        renderer.render_agenda(events, title=title, subtitle=subtitle)
    else:
        renderer.render_list(events, title=title, subtitle=subtitle)
