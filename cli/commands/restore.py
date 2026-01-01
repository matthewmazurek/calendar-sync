"""Restore calendar to specific git commit."""

import logging
import sys
from datetime import timezone

from app.config import CalendarConfig
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage

logger = logging.getLogger(__name__)


def restore_command(name: str, commit: str, force: bool = False) -> None:
    """
    Restore calendar to specific git commit, version number, or relative command.
    
    Args:
        name: Calendar name
        commit: Git commit hash, version number (#3 or 3), or relative command (latest, previous)
        force: If True, skip confirmation prompt
    """
    config = CalendarConfig.from_env()
    storage = CalendarStorage(config)
    repository = CalendarRepository(config.calendar_dir, storage)

    # Check if calendar has any versions in git history (works for deleted calendars too)
    versions = repository.list_calendar_versions(name)
    if not versions:
        logger.error(f"Calendar '{name}' not found in git history")
        sys.exit(1)

    # Parse commit input - could be version number, relative command, or commit hash
    target_commit = None
    commit_display = commit
    
    # Check for version number (#3 or 3)
    if commit.startswith("#"):
        try:
            version_num = int(commit[1:])
            if version_num < 1 or version_num > len(versions):
                logger.error(f"Version #{version_num} not found. Available versions: 1-{len(versions)}")
                sys.exit(1)
            target_commit = versions[version_num - 1][0]  # versions are 0-indexed
            commit_display = f"#{version_num} ({target_commit[:7]})"
        except ValueError:
            pass  # Not a valid version number, treat as commit hash
    elif commit.isdigit():
        try:
            version_num = int(commit)
            if version_num < 1 or version_num > len(versions):
                logger.error(f"Version #{version_num} not found. Available versions: 1-{len(versions)}")
                sys.exit(1)
            target_commit = versions[version_num - 1][0]
            commit_display = f"#{version_num} ({target_commit[:7]})"
        except ValueError:
            pass  # Not a valid version number, treat as commit hash
    elif commit.lower() == "latest":
        target_commit = versions[0][0]  # Most recent version
        commit_display = f"latest ({target_commit[:7]})"
    elif commit.lower() == "previous":
        if len(versions) < 2:
            logger.error(f"Only {len(versions)} version(s) available. Cannot restore to previous.")
            sys.exit(1)
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
        sys.exit(1)

    commit_hash, commit_date, commit_message = commit_info

    # Show confirmation prompt unless --force is set
    if not force:
        # Format commit date
        if commit_date.tzinfo is None:
            commit_date = commit_date.replace(tzinfo=timezone.utc)
        date_str = commit_date.strftime("%Y-%m-%d %H:%M")
        
        print(f"Will restore calendar '{name}' to:")
        print(f"  Version: {commit_display}")
        print(f"  Date: {date_str}")
        print(f"  Message: {commit_message}")
        print()
        
        response = input("Continue? [y/N]: ")
        if response.lower() not in ['y', 'yes']:
            print("Restore cancelled.")
            return

    # Get calendar directory (even if it doesn't exist yet)
    calendar_dir = repository._get_calendar_dir(name)

    # Ensure calendar directory exists (for deleted calendars)
    calendar_dir.mkdir(parents=True, exist_ok=True)

    # Restore entire directory from git (includes calendar.ics, metadata.json, etc.)
    git_service = repository.git_service
    if git_service.restore_directory_version(calendar_dir, target_commit):
        print(f"Calendar '{name}' restored to {commit_display}")
    else:
        logger.error(f"Failed to restore calendar '{name}' to {commit_display}")
        sys.exit(1)
