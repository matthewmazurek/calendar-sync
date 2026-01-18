"""Analyze calendar events: counts by type, coverage metrics, and scheduling patterns."""

import typer
from typing_extensions import Annotated

from app.ingestion.summary import build_calendar_statistics
from cli.context import get_context
from cli.display.stats_renderer import StatsRenderer
from cli.utils import require_calendar_with_data


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
    include_non_busy: Annotated[
        bool,
        typer.Option(
            "--include-non-busy",
            "-b",
            help="Include non-busy events (holidays, vacation) in coverage",
        ),
    ] = False,
    include_other: Annotated[
        bool,
        typer.Option(
            "--include-other",
            "-o",
            help="Include 'other' type events in coverage",
        ),
    ] = False,
) -> None:
    """Analyze calendar events: counts by type, coverage metrics, and scheduling patterns.

    Use 'info' instead to view calendar metadata (path, timestamps, git history).
    """
    ctx = get_context()
    repository = ctx.repository
    renderer = StatsRenderer()

    calendar = require_calendar_with_data(repository, name)

    # Build statistics
    stats_data = build_calendar_statistics(
        calendar,
        year=year,
        include_non_busy=include_non_busy,
        include_other=include_other,
    )

    # Render statistics
    renderer.render_statistics(
        stats_data,
        calendar_name=name,
        year=year,
        show_weeks=show_weeks,
    )
