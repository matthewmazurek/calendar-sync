"""Search calendar events by text, type, or location."""

import logging

import typer
from typing_extensions import Annotated

from app.calendar_query import CalendarQuery
from cli.context import get_context
from cli.display import RichEventRenderer

logger = logging.getLogger(__name__)


def search(
    name: Annotated[
        str,
        typer.Argument(help="Calendar name"),
    ],
    query: Annotated[
        str | None,
        typer.Argument(help="Text to search for in event titles"),
    ] = None,
    event_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Filter by event type"),
    ] = None,
    location: Annotated[
        str | None,
        typer.Option("--location", "-l", help="Filter by location"),
    ] = None,
    year: Annotated[
        int | None,
        typer.Option("--year", "-y", help="Filter by year"),
    ] = None,
    future: Annotated[
        bool,
        typer.Option("--future", "-f", help="Filter to future events only"),
    ] = False,
    days: Annotated[
        int | None,
        typer.Option("--days", "-d", help="Limit to next N days (implies --future)"),
    ] = None,
) -> None:
    """Search calendar events.

    Search by text (matches event titles), filter by type or location,
    and optionally limit to a specific year or number of days.

    Examples:
        calsync search <calendar> clinic           # Find events with "clinic" in title
        calsync search <calendar> --type endo      # Find all endoscopy events
        calsync search <calendar> --location work  # Find events at "work" location
        calsync search <calendar> admin --year 2026    # Admin events in 2026
        calsync search <calendar> --type on_call -f    # Future on-call events
        calsync search <calendar> --type on_call -d 30 # On-call in next 30 days
    """
    ctx = get_context()
    repository = ctx.repository

    # Validate that at least one search criterion is provided
    if not any([query, event_type, location]):
        logger.error("Please provide a search query, --type, or --location")
        raise typer.Exit(1)

    # Load calendar
    calendar_with_metadata = repository.load_calendar(name)
    if calendar_with_metadata is None:
        logger.error(f"Calendar '{name}' not found")
        raise typer.Exit(1)

    calendar = calendar_with_metadata.calendar
    cal_query = CalendarQuery(calendar)
    renderer = RichEventRenderer()

    # Apply search filters
    events = cal_query.search(query=query, event_type=event_type, location=location)

    # Apply additional filters
    if year:
        events = [e for e in events if e.date.year == year]

    # Filter to future events (--future or --days implies this)
    if future or days:
        from datetime import date, timedelta

        today = date.today()
        if days:
            # Limit to next N days
            end_date = today + timedelta(days=days)
            events = [e for e in events if today <= e.date <= end_date]
        else:
            # Just filter to future events (today onwards)
            events = [e for e in events if e.date >= today]

    # Build title and subtitle
    title = f"Search: {name}"

    # Build subtitle from search criteria
    criteria = []
    if query:
        criteria.append(f'"{query}"')
    if event_type:
        criteria.append(f"type: {event_type}")
    if location:
        criteria.append(f"location: {location}")
    if year:
        criteria.append(str(year))
    if days:
        criteria.append(f"next {days} days")
    elif future:
        criteria.append("future")

    subtitle = " ".join(criteria) if criteria else None

    # Render results using list view (best for search results)
    if events:
        renderer.render_list(events, title=title, subtitle=subtitle)
    else:
        renderer.render_empty(f"No events matching: {subtitle}")
