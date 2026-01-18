"""CLI utilities for user interaction."""

from typing import TYPE_CHECKING

import typer

from cli.display.console import console

if TYPE_CHECKING:
    from app.models.calendar import Calendar
    from app.storage.calendar_repository import CalendarRepository


def confirm_or_exit(prompt: str = "Continue?", force: bool = False) -> None:
    """Prompt for confirmation unless force is True. Exits if declined.

    Args:
        prompt: The confirmation prompt to display.
        force: If True, skip the confirmation prompt.
    """
    if not force:
        typer.echo()
        if not typer.confirm(prompt):
            typer.echo("Operation cancelled.")
            raise typer.Exit(0)


def require_calendar_with_data(
    repository: "CalendarRepository",
    name: str,
) -> "Calendar":
    """Load a calendar, ensuring it exists and has data.

    Checks that:
    1. Calendar exists (has config.json)
    2. Calendar has data (has data.json)

    Args:
        repository: CalendarRepository instance
        name: Calendar name

    Returns:
        Calendar if found

    Raises:
        typer.Exit(1): If calendar doesn't exist or has no data
    """
    # Check if calendar exists (has config.json)
    if not repository.calendar_exists(name):
        console.print(f"\n[red]Calendar '{name}' not found[/red]")
        raise typer.Exit(1)

    # Check if calendar has data (has data.json)
    calendar = repository.load_calendar(name)
    if calendar is None:
        console.print(
            f"\n[yellow]Calendar '{name}' has no data.[/yellow]\n"
            f"Run [cyan]calsync ingest {name} <source>[/cyan] to add events."
        )
        raise typer.Exit(1)

    return calendar
