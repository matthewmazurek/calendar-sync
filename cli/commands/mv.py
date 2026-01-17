"""Rename a calendar."""

import logging

import typer
from typing_extensions import Annotated

from app.exceptions import CalendarNotFoundError
from cli.context import get_context
from cli.display import console

logger = logging.getLogger(__name__)


def mv(
    old_name: Annotated[
        str,
        typer.Argument(help="Current calendar name"),
    ],
    new_name: Annotated[
        str,
        typer.Argument(help="New calendar name"),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Rename a calendar.

    Renames the calendar directory and updates internal references.

    Example:
        calsync mv old-calendar new-calendar
    """
    ctx = get_context()
    repository = ctx.repository
    git_service = ctx.git_service

    # Validate source exists
    if not repository.calendar_exists(old_name):
        logger.error(f"Calendar '{old_name}' not found")
        raise typer.Exit(1)

    # Validate target doesn't exist
    if repository.calendar_exists(new_name):
        logger.error(f"Calendar '{new_name}' already exists")
        raise typer.Exit(1)

    # Confirmation prompt
    if not force:
        console.print(f"\nRename calendar '{old_name}' → '{new_name}'")
        console.print()
        if not typer.confirm("Continue?"):
            console.print("Rename cancelled.")
            return

    try:
        repository.rename_calendar(old_name, new_name)
    except CalendarNotFoundError as e:
        logger.error(str(e))
        raise typer.Exit(1)
    except ValueError as e:
        logger.error(str(e))
        raise typer.Exit(1)

    # Commit the rename to git
    git_service.commit_rename(old_name, new_name)

    console.print(
        f"\n[bold green]✓[/bold green] Calendar renamed: '{old_name}' → '{new_name}'"
    )
