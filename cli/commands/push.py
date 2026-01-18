"""Push an existing calendar to git."""

import logging

import typer
from typing_extensions import Annotated

from cli.context import get_context
from cli.display import push_calendar

logger = logging.getLogger(__name__)


def push(
    calendar_name: Annotated[
        str,
        typer.Argument(help="Name of calendar to push"),
    ],
) -> None:
    """Push an existing calendar to git."""
    ctx = get_context()
    config = ctx.config
    repository = ctx.repository
    git_service = ctx.git_service

    # ─────────────────────────────────────────────────────────────────────────
    # Load and validate calendar
    # ─────────────────────────────────────────────────────────────────────────
    calendar = repository.load_calendar(calendar_name)
    if calendar is None:
        typer.echo(
            f"{typer.style('✗', fg=typer.colors.RED, bold=True)} Calendar '{calendar_name}' not found"
        )
        raise typer.Exit(1)

    calendar_path = repository.get_calendar_path(calendar_name)
    if calendar_path is None:
        typer.echo(
            f"{typer.style('✗', fg=typer.colors.RED, bold=True)} No calendar file found for '{calendar_name}'"
        )
        raise typer.Exit(1)

    # ─────────────────────────────────────────────────────────────────────────
    # Push with expressive output
    # ─────────────────────────────────────────────────────────────────────────
    remote_url = config.calendar_git_remote_url or git_service.get_remote_url()
    event_count = len(calendar.events)

    success = push_calendar(
        git_service=git_service,
        calendar_name=calendar_name,
        calendar_path=calendar_path,
        event_count=event_count,
        remote_url=remote_url,
        show_header=True,
    )

    if not success:
        raise typer.Exit(1)
