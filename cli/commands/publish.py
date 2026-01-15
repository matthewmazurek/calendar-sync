"""Publish an existing calendar to git."""

import logging

import typer
from typing_extensions import Annotated

from cli.context import get_context

logger = logging.getLogger(__name__)


def publish(
    calendar_name: Annotated[
        str,
        typer.Argument(help="Name of calendar to publish"),
    ],
    format: Annotated[
        str,
        typer.Option("--format", help="Calendar format (ics or json)"),
    ] = "ics",
) -> None:
    """Publish an existing calendar to git."""
    ctx = get_context()
    config = ctx.config
    repository = ctx.repository
    git_service = ctx.git_service

    # Load calendar to verify it exists
    calendar_with_metadata = repository.load_calendar(calendar_name, format)
    if calendar_with_metadata is None:
        logger.error(f"Calendar '{calendar_name}' not found")
        raise typer.Exit(1)

    # Get latest filepath
    latest_path = repository.get_calendar_path(calendar_name, format)
    if latest_path is None:
        logger.error(f"No calendar file found for '{calendar_name}'")
        raise typer.Exit(1)

    # Check if remote is configured
    if not config.calendar_git_remote_url and not git_service.get_remote_url():
        typer.echo("Warning: No remote URL configured. Calendar will be committed locally but not pushed.")
        typer.echo("Run 'calendar-sync git-setup' to configure a remote repository.")
    
    git_service.publish_calendar(calendar_name, latest_path, format)
