"""Show calendar metadata: storage path, timestamps, git history, and subscription URL."""

import logging
from datetime import date, datetime, timezone

import typer
from typing_extensions import Annotated

from app.storage.subscription_url_generator import SubscriptionUrlGenerator
from cli.context import get_context
from cli.display import format_relative_time

logger = logging.getLogger(__name__)


def _format_datetime(dt, include_relative=True):
    """Format datetime or date with optional relative time."""
    if dt is None:
        return "N/A"

    # Handle date objects (no time component)
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")

    # Handle datetime objects
    # Ensure timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    if include_relative:
        relative = format_relative_time(dt)
        return f"{date_str} ({relative})"
    return date_str


def info(
    name: Annotated[
        str,
        typer.Argument(help="Calendar name"),
    ],
) -> None:
    """Show calendar metadata: storage path, timestamps, git history, and subscription URL.

    Use 'stats' instead to analyze event data (counts by type, coverage metrics).
    """
    ctx = get_context()
    repository = ctx.repository
    git_service = ctx.git_service

    calendar_with_metadata = repository.load_calendar(name)
    if calendar_with_metadata is None:
        print(f"\nCalendar '{name}' not found")
        raise typer.Exit(1)

    calendar = calendar_with_metadata.calendar
    metadata = calendar_with_metadata.metadata

    # Get calendar path (ICS export)
    calendar_path = repository.get_calendar_path(name)

    # ─────────────────────────────────────────────────────────────────────────
    # Header
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'━' * 40}")
    print(typer.style(f"  Calendar: {name}", bold=True))
    print(f"{'━' * 40}")

    # ─────────────────────────────────────────────────────────────────────────
    # Overview
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\nPath: {calendar_path.resolve()}")

    # Calculate date range from events
    if calendar.events:
        dates = [event.date for event in calendar.events]
        min_date = min(dates)
        max_date = max(dates)
        date_range = f"{min_date} to {max_date}"
    else:
        date_range = "no events"

    print(f"  {len(calendar.events):,} events · {date_range}")

    # Template info
    if metadata.template_name:
        template_info = metadata.template_name
        if metadata.template_version:
            template_info += f" v{metadata.template_version}"
        print(f"  Template: {template_info}")

    # ─────────────────────────────────────────────────────────────────────────
    # Timestamps
    # ─────────────────────────────────────────────────────────────────────────
    print("\nTimestamps:")
    label_width = 16
    if metadata.source_revised_at:
        print(
            f"  {'Source revised:':<{label_width}} {_format_datetime(metadata.source_revised_at)}"
        )
    print(f"  {'Created:':<{label_width}} {_format_datetime(metadata.created)}")
    print(
        f"  {'Last updated:':<{label_width}} {_format_datetime(metadata.last_updated)}"
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Git information
    # ─────────────────────────────────────────────────────────────────────────
    versions = repository.list_calendar_versions(name)
    commit_count = len(versions)

    print("\nGit:")
    if commit_count > 0:
        print(f"  {'Commits:':<{label_width}} {commit_count}")

        # Get latest commit info
        latest_commit_hash, latest_commit_date, latest_commit_message = versions[0]

        # Get current version (what's in working directory) - use canonical path
        canonical_path = repository._get_canonical_path(name)
        current_commit_hash = None
        if canonical_path.exists():
            current_commit_hash = repository.git_service.get_current_commit_hash(
                canonical_path
            )

        # Show current version
        if current_commit_hash:
            # Find the commit date for current version
            current_commit_date = None
            for commit_hash, commit_date, _ in versions:
                if commit_hash == current_commit_hash:
                    current_commit_date = commit_date
                    break

            if current_commit_date:
                current_str = f"{current_commit_hash[:7]} ({_format_datetime(current_commit_date, include_relative=False)})"
            else:
                current_str = current_commit_hash[:7]
        else:
            current_str = "uncommitted changes"

        print(f"  {'Current:':<{label_width}} {current_str}")
        print(
            f"  {'Latest:':<{label_width}} {latest_commit_hash[:7]} ({_format_datetime(latest_commit_date, include_relative=False)})"
        )

        # Show remote URL if available
        if calendar_path:
            url_generator = SubscriptionUrlGenerator(
                git_service.repo_root, git_service.remote_url
            )
            subscription_urls = url_generator.generate_subscription_urls(
                name, calendar_path, "ics"
            )
            if subscription_urls:
                print(f"\n  {'Remote URL:':<{label_width}} {subscription_urls[0]}")
    else:
        print(f"  Not in a git repository")
