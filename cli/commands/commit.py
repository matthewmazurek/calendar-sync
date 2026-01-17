"""Commit calendar files to git."""

import logging
import sys

import typer
from typing_extensions import Annotated

from cli.context import get_context

logger = logging.getLogger(__name__)


def commit_command(
    calendar_name: Annotated[
        str,
        typer.Argument(help="Calendar name to commit"),
    ],
    message: Annotated[
        str | None,
        typer.Option("--message", "-m", help="Custom commit message"),
    ] = None,
) -> None:
    """
    Commit calendar files to git.

    This is a pure git operation that stages and commits all files
    in the calendar directory (data.json, calendar.ics, config.json, etc.)
    without generating or modifying any files.

    The commit is local only. Use 'push' to push to remote.
    """
    ctx = get_context()
    repository = ctx.repository
    git_service = ctx.git_service

    # Get paths for this calendar
    paths = repository.paths(calendar_name)

    # Check if calendar directory exists
    if not paths.directory.exists():
        logger.error(f"Calendar directory not found: {paths.directory.resolve()}")
        sys.exit(1)

    # Check what files exist
    files_to_commit = []
    if paths.data.exists():
        files_to_commit.append(paths.data.name)
    if paths.export("ics").exists():
        files_to_commit.append(paths.export("ics").name)

    if not files_to_commit:
        print(f"No calendar files found in {paths.directory.resolve()}")
        sys.exit(1)

    print(f"Files to commit: {', '.join(files_to_commit)}")

    # Commit using git service
    try:
        git_service.commit_calendar_locally(calendar_name, message=message)

        print(f"{typer.style('✓', fg=typer.colors.GREEN, bold=True)} Committed to git")
        print(f"  Calendar: {calendar_name}")

        logger.info(f"Committed calendar '{calendar_name}' to git")

    except Exception as e:
        logger.error(f"Commit failed: {e}")
        sys.exit(1)


# Alias for CLI registration
commit = commit_command
