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
        typer.Option(
            "--message", "-m", help="Custom commit message"
        ),
    ] = None,
) -> None:
    """
    Commit calendar files to git.
    
    This is a pure git operation that stages and commits whatever files
    exist in the calendar directory (calendar_data.json, calendar.ics, etc.)
    without generating or modifying any files.
    
    The commit is local only. Use 'push' to push to remote.
    """
    ctx = get_context()
    repository = ctx.repository
    git_service = ctx.git_service

    # Check if calendar directory exists
    calendar_dir = repository._get_calendar_dir(calendar_name)
    if not calendar_dir.exists():
        logger.error(f"Calendar directory not found: {calendar_dir}")
        sys.exit(1)

    # Check what files exist
    canonical_path = repository._get_canonical_path(calendar_name)
    ics_path = repository._get_ics_export_path(calendar_name)
    
    files_to_commit = []
    if canonical_path.exists():
        files_to_commit.append(canonical_path.name)
    if ics_path.exists():
        files_to_commit.append(ics_path.name)
    
    if not files_to_commit:
        print(f"No calendar files found in {calendar_dir}")
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
