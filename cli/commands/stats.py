"""Analyze calendar events: counts by type, coverage metrics, and scheduling patterns."""

import typer
from typing_extensions import Annotated

from app.ingestion.summary import build_calendar_statistics
from cli.context import get_context
from cli.display.stats_renderer import StatsRenderer


def stats(
    name: Annotated[
        str,
        typer.Argument(help="Calendar name"),
    ],
    year: Annotated[
        int | None,
        typer.Option("--year", "-y", help="Filter events by year"),
    ] = None,
    show_weeks: Annotated[
        bool,
        typer.Option("--weeks", "-w", help="Show half-days breakdown by week"),
    ] = False,
) -> None:
    """Analyze calendar events: counts by type, coverage metrics, and scheduling patterns.

    Use 'info' instead to view calendar metadata (path, timestamps, git history).
    """
    ctx = get_context()
    repository = ctx.repository
    renderer = StatsRenderer()

    calendar_with_metadata = repository.load_calendar(name)
    if calendar_with_metadata is None:
        renderer.render_not_found(name)
        raise typer.Exit(1)

    calendar = calendar_with_metadata.calendar

    # Build statistics
    stats_data = build_calendar_statistics(calendar, year=year)

    # Render statistics
    renderer.render_statistics(
        stats_data,
        calendar_name=name,
        year=year,
        show_weeks=show_weeks,
    )
