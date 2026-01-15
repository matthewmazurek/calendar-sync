"""Display calendar info and event count."""

import logging
from datetime import date, datetime, timezone

import typer
from typing_extensions import Annotated

from app.storage.subscription_url_generator import SubscriptionUrlGenerator
from cli.context import get_context
from cli.utils import format_relative_time

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
    """Display calendar info and event count."""
    ctx = get_context()
    repository = ctx.repository
    git_service = ctx.git_service

    calendar_with_metadata = repository.load_calendar(name)
    if calendar_with_metadata is None:
        logger.error(f"Calendar '{name}' not found")
        raise typer.Exit(1)

    calendar = calendar_with_metadata.calendar
    metadata = calendar_with_metadata.metadata

    # Get calendar path
    calendar_path = repository.get_calendar_path(name, metadata.format)

    # Header
    typer.echo(f"Calendar: {name} ({calendar_path})")
    typer.echo()

    # Basic info
    label_width = 18
    typer.echo(f"{'Events:':<{label_width}} {len(calendar.events):,}")
    typer.echo(f"{'Format:':<{label_width}} {metadata.format}")

    # Calculate date range from events
    if calendar.events:
        dates = [event.date for event in calendar.events]
        min_date = min(dates)
        max_date = max(dates)
        typer.echo(f"{'Date range:':<{label_width}} {min_date} to {max_date}")
    else:
        typer.echo(f"{'Date range:':<{label_width}} no events")

    typer.echo()

    # Timestamps
    if metadata.source_revised_at:
        typer.echo(
            f"{'Source revised:':<{label_width}} {_format_datetime(metadata.source_revised_at)}"
        )
    typer.echo(f"{'Created:':<{label_width}} {_format_datetime(metadata.created)}")
    typer.echo(f"{'Last updated:':<{label_width}} {_format_datetime(metadata.last_updated)}")

    # Get git commit history to show actual commit count
    versions = repository.list_calendar_versions(name, metadata.format)
    commit_count = len(versions)

    if commit_count > 0:
        typer.echo()
        typer.echo(f"{'Git commits:':<{label_width}} {commit_count}")

        # Get latest commit info
        latest_commit_hash, latest_commit_date, latest_commit_message = versions[0]

        # Get current version (what's in working directory)
        calendar_path = repository.get_calendar_path(name, metadata.format)
        current_commit_hash = None
        if calendar_path:
            current_commit_hash = repository.git_service.get_current_commit_hash(
                calendar_path
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
                current_str = (
                    f"{current_commit_hash[:7]} {_format_datetime(current_commit_date)}"
                )
            else:
                current_str = current_commit_hash[:7]
        else:
            current_str = "uncommitted changes"

        typer.echo(f"{'Current version:':<{label_width}} {current_str}")
        typer.echo(
            f"{'Latest commit:':<{label_width}} {latest_commit_hash[:7]} {_format_datetime(latest_commit_date)}"
        )

        # Show remote URL if available
        if calendar_path:
            url_generator = SubscriptionUrlGenerator(
                git_service.repo_root, git_service.remote_url
            )
            subscription_urls = url_generator.generate_subscription_urls(
                name, calendar_path, metadata.format
            )
            if subscription_urls:
                typer.echo(f"{'Remote URL:':<{label_width}} {subscription_urls[0]}")
    else:
        typer.echo()
        typer.echo(f"{'Git commits:':<{label_width}} N/A (not in git repository)")
