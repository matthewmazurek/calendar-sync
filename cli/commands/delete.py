"""Delete a calendar."""

import logging

import typer
from typing_extensions import Annotated

from cli.context import get_context

logger = logging.getLogger(__name__)


def delete(
    name: Annotated[
        str,
        typer.Argument(help="Calendar name to delete"),
    ],
    purge_history: Annotated[
        bool,
        typer.Option(
            "--purge-history",
            help="Remove calendar from git history entirely (hard delete, rewrites history)",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Delete a calendar."""
    ctx = get_context()
    repository = ctx.repository
    git_service = ctx.git_service

    calendar_dir = repository._get_calendar_dir(name)
    calendar_exists = calendar_dir.exists()

    # Show confirmation prompt unless --force is set
    if not force:
        print(f"\nDelete calendar '{name}'")
        print(f"  Directory: {calendar_dir}")

        if purge_history:
            print(
                f"\n{typer.style('⚠', fg=typer.colors.YELLOW, bold=True)} "
                "This will permanently remove from git history (rewrites history)"
            )
        else:
            print("\n  The calendar will be archived in git history.")
            print("  You can restore it later using: calendar-sync restore")

        print()
        if not typer.confirm("Continue?"):
            typer.echo("Delete cancelled.")
            return

    if purge_history:
        # Hard delete: remove from git history entirely
        # This works even if calendar was already deleted from filesystem
        typer.echo(f"Purging calendar '{name}' from git history...")
        if git_service.purge_from_history(name):
            # After purging from history, remove from filesystem if it still exists
            if calendar_exists:
                repository.delete_calendar(name)
            print(
                f"\n{typer.style('✓', fg=typer.colors.GREEN, bold=True)} "
                f"Calendar '{name}' purged from git history"
            )
        else:
            logger.error(f"Failed to purge calendar '{name}' from git history")
            raise typer.Exit(1)
    else:
        # Regular delete: requires calendar to exist
        if not calendar_exists:
            logger.error(f"Calendar '{name}' not found")
            raise typer.Exit(1)

        # Remove from filesystem and commit deletion to git
        repository.delete_calendar(name)
        # Commit the deletion to git for audit trail
        git_service.commit_deletion(name)
        print(
            f"\n{typer.style('✓', fg=typer.colors.GREEN, bold=True)} "
            f"Calendar '{name}' deleted (archived in git history)"
        )
