"""Create a new calendar."""

import logging

import typer
from typing_extensions import Annotated

from cli.context import get_context
from cli.display import console

logger = logging.getLogger(__name__)


def new(
    calendar_id: Annotated[
        str,
        typer.Argument(help="Calendar ID (directory name)"),
    ],
    name: Annotated[
        str | None,
        typer.Option(
            "--name", "-n", help="Display name (defaults to ID if not set)"
        ),
    ] = None,
    template: Annotated[
        str | None,
        typer.Option(
            "--template", "-t", help="Default template for this calendar"
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option(
            "--description", "-d", help="Human-readable description"
        ),
    ] = None,
) -> None:
    """Create a new calendar.

    Creates a calendar directory with a config.json file containing
    the specified settings. No data ingestion is required.

    Example:
        calsync new work --name "Work Schedule" --template work-schedule
    """
    ctx = get_context()
    repository = ctx.repository

    # Check if calendar already exists
    if repository.calendar_exists(calendar_id):
        logger.error(f"Calendar '{calendar_id}' already exists")
        raise typer.Exit(1)

    try:
        settings_path = repository.create_calendar(
            calendar_id=calendar_id,
            name=name,
            template=template,
            description=description,
        )
    except ValueError as e:
        logger.error(str(e))
        raise typer.Exit(1)

    # Success message
    display_name = name or calendar_id
    console.print(
        f"\n[bold green]✓[/bold green] Calendar '{display_name}' created"
    )
    console.print(f"  ID: {calendar_id}")
    console.print(f"  Config: {settings_path}")

    if name:
        console.print(f"  Name: {name}")
    if template:
        console.print(f"  Template: {template}")
    if description:
        console.print(f"  Description: {description}")

    console.print(f"\n[bold]Next steps:[/bold]")
    console.print(f"  • Run 'ingest {calendar_id} <file>' to add calendar data")
