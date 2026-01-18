"""Restore calendar to specific git commit."""

import logging
from datetime import timezone

import typer
from typing_extensions import Annotated

from app.models.template_loader import get_template
from cli.commands.diff import display_diff
from cli.context import get_context

logger = logging.getLogger(__name__)


def restore(
    name: Annotated[
        str,
        typer.Argument(help="Calendar name"),
    ],
    commit: Annotated[
        str,
        typer.Argument(
            help="Git commit hash, version number (#3 or 3), or relative command (latest, previous)"
        ),
    ] = "previous",
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Restore calendar to specific git commit, version number, or relative command."""
    ctx = get_context()
    repository = ctx.repository
    git_service = ctx.git_service

    # Check if calendar has any versions in git history (works for deleted calendars too)
    versions = repository.list_calendar_versions(name)
    if not versions:
        logger.error(f"Calendar '{name}' not found in git history")
        raise typer.Exit(1)

    # Parse commit input - could be version number, relative command, or commit hash
    target_commit = None
    commit_display = commit

    # Check for version number (#3 or 3)
    if commit.startswith("#"):
        try:
            version_num = int(commit[1:])
            if version_num < 1 or version_num > len(versions):
                logger.error(
                    f"Version #{version_num} not found. Available versions: 1-{len(versions)}"
                )
                raise typer.Exit(1)
            target_commit = versions[version_num - 1][0]  # versions are 0-indexed
            commit_display = f"#{version_num} ({target_commit[:7]})"
        except ValueError:
            pass  # Not a valid version number, treat as commit hash
    elif commit.isdigit():
        try:
            version_num = int(commit)
            if version_num < 1 or version_num > len(versions):
                logger.error(
                    f"Version #{version_num} not found. Available versions: 1-{len(versions)}"
                )
                raise typer.Exit(1)
            target_commit = versions[version_num - 1][0]
            commit_display = f"#{version_num} ({target_commit[:7]})"
        except ValueError:
            pass  # Not a valid version number, treat as commit hash
    elif commit.lower() == "latest":
        target_commit = versions[0][0]  # Most recent version
        commit_display = f"latest ({target_commit[:7]})"
    elif commit.lower() == "previous":
        if len(versions) < 2:
            logger.error(
                f"Only {len(versions)} version(s) available. Cannot restore to previous."
            )
            raise typer.Exit(1)
        target_commit = versions[1][0]  # Second most recent version
        commit_display = f"previous ({target_commit[:7]})"
    else:
        # Treat as commit hash - find matching commit
        target_commit = commit
        # Try to find full commit hash if partial hash provided
        for v_hash, _, _ in versions:
            if v_hash.startswith(commit):
                target_commit = v_hash
                commit_display = target_commit[:7] if len(commit) < 7 else commit
                break

    # Get commit info for confirmation
    commit_info = None
    for v_hash, v_date, v_message in versions:
        if v_hash == target_commit:
            commit_info = (v_hash, v_date, v_message)
            break

    if commit_info is None:
        logger.error(f"Commit '{commit}' not found for calendar '{name}'")
        raise typer.Exit(1)

    commit_hash, commit_date, commit_message = commit_info

    # Format commit date
    if commit_date.tzinfo is None:
        commit_date = commit_date.replace(tzinfo=timezone.utc)
    date_str = commit_date.strftime("%Y-%m-%d %H:%M")

    # Load current calendar (before restore) for diff
    current_result = repository.load_calendar(name)
    current_calendar = current_result.calendar if current_result else None

    # Load target calendar version for diff preview
    target_result = repository.load_calendar_by_commit(name, target_commit)
    target_calendar = target_result.calendar if target_result else None

    # Show confirmation prompt unless --force is set
    if not force:
        print(f"\nRestore calendar '{name}' to:")
        print(f"  Version: {commit_display}")
        print(f"  Date: {date_str}")
        print(f"  Message: {commit_message}")

        # Show diff preview
        display_diff(current_calendar, target_calendar, "current", "restored")

        print()
        if not typer.confirm("Continue?"):
            typer.echo("Restore cancelled.")
            return

    # Get paths for this calendar (even if it doesn't exist yet)
    paths = repository.paths(name)

    # Ensure calendar directory exists (for deleted calendars)
    paths.directory.mkdir(parents=True, exist_ok=True)

    # Restore entire directory from git (includes calendar_data.json, calendar.ics, etc.)
    if git_service.restore_directory_version(paths.directory, target_commit):
        # Get path for clickable link (ICS export file)
        calendar_path = paths.export("ics")

        # Re-export ICS to ensure location_id references are resolved
        # (for calendars that use location_id)
        try:
            restored = repository.load_calendar(name)
            if restored and restored.metadata.template_name:
                template = get_template(
                    restored.metadata.template_name, ctx.config.template_dir
                )
                repository.export_ics(name, template=template)
                logger.info("Re-exported ICS with template resolution")
        except Exception as e:
            logger.debug(f"ICS re-export skipped: {e}")

        # Show diff after restore when using --force
        if force:
            display_diff(current_calendar, target_calendar, "previous", "restored")

        print(
            f"\n{typer.style('✓', fg=typer.colors.GREEN, bold=True)} Calendar restored to {commit_display}"
        )
        print(f"  {calendar_path.resolve()}")
    else:
        logger.error(f"Failed to restore calendar '{name}' to {commit_display}")
        raise typer.Exit(1)
