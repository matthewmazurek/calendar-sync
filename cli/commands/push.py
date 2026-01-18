"""Push an existing calendar to git."""

import logging
import sys

import typer
from typing_extensions import Annotated

from app.exceptions import GitCommandError, GitError
from app.storage.subscription_url_generator import SubscriptionUrlGenerator
from cli.context import get_context

logger = logging.getLogger(__name__)


def push(
    calendar_name: Annotated[
        str,
        typer.Argument(help="Name of calendar to push"),
    ],
) -> None:
    """Push an existing calendar to git."""
    ctx = get_context()
    config = ctx.config
    repository = ctx.repository
    git_service = ctx.git_service

    # ─────────────────────────────────────────────────────────────────────────
    # Load and validate calendar
    # ─────────────────────────────────────────────────────────────────────────
    calendar = repository.load_calendar(calendar_name)
    if calendar is None:
        typer.echo(
            f"{typer.style('✗', fg=typer.colors.RED, bold=True)} Calendar '{calendar_name}' not found"
        )
        raise typer.Exit(1)

    latest_path = repository.get_calendar_path(calendar_name)
    if latest_path is None:
        typer.echo(
            f"{typer.style('✗', fg=typer.colors.RED, bold=True)} No calendar file found for '{calendar_name}'"
        )
        raise typer.Exit(1)

    # ─────────────────────────────────────────────────────────────────────────
    # Header
    # ─────────────────────────────────────────────────────────────────────────
    event_count = len(calendar.events)

    print(f"\n{'━' * 40}")
    print(typer.style(f"  Pushing: {calendar_name}", bold=True))
    print(f"{'━' * 40}")

    # Calendar info
    print(f"\nCalendar: {latest_path.resolve()}")
    print(f"  {event_count} events")

    # ─────────────────────────────────────────────────────────────────────────
    # Check remote configuration
    # ─────────────────────────────────────────────────────────────────────────
    remote_url = config.calendar_git_remote_url or git_service.get_remote_url()
    if not remote_url:
        print(
            f"\n{typer.style('⚠', fg=typer.colors.YELLOW, bold=True)} No remote URL configured"
        )
        print("  Calendar will be committed locally but not pushed.")
        print("  Run 'calendar-sync git-setup' to configure a remote repository.")
        print()

    # ─────────────────────────────────────────────────────────────────────────
    # Push steps
    # ─────────────────────────────────────────────────────────────────────────
    print("\nPushing...")

    try:
        # Step 1: Commit locally
        print("  Staging and committing changes...", end=" ", flush=True)
        git_service.commit_calendar_locally(calendar_name)
        print(typer.style("done", fg=typer.colors.GREEN))

        # Step 2: Push to remote (only if remote is configured)
        if remote_url:
            print("  Pushing to remote...", end=" ", flush=True)
            git_service._push_changes()
            print(typer.style("done", fg=typer.colors.GREEN))

        # Success message
        print(
            f"\n{typer.style('✓', fg=typer.colors.GREEN, bold=True)} Calendar pushed successfully"
        )

        # ─────────────────────────────────────────────────────────────────────
        # Generate and display subscription URLs
        # ─────────────────────────────────────────────────────────────────────
        if remote_url:
            url_generator = SubscriptionUrlGenerator(
                git_service.repo_root, git_service.remote_url
            )
            urls = url_generator.generate_subscription_urls(
                calendar_name, latest_path, "ics"
            )
            if urls:
                print("\nSubscription URLs:")
                for url in urls:
                    print(f"  {typer.style(url, fg=typer.colors.CYAN)}")
        else:
            print("\n  (Subscription URLs not available without remote)")

    except (GitError, GitCommandError) as e:
        print(typer.style("failed", fg=typer.colors.RED))
        print(
            f"\n{typer.style('✗', fg=typer.colors.RED, bold=True)} Git operation failed: {e}",
            file=sys.stderr,
        )
        raise typer.Exit(1)
