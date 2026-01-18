"""Push renderer for git push operations."""

from pathlib import Path

import typer

from app.exceptions import GitCommandError, GitError
from app.storage.git_service import GitService
from app.storage.subscription_url_generator import SubscriptionUrlGenerator
from cli.display.console import console


class PushRenderer:
    """Render push operation output with step-by-step progress.

    Provides expressive output for git push operations including:
    - Header with calendar name
    - Calendar info (path and event count)
    - Remote configuration warnings
    - Step-by-step progress indicators
    - Success/failure messages
    - Subscription URLs
    """

    def render_header(self, calendar_name: str) -> None:
        """Render push header.

        Args:
            calendar_name: Name of the calendar being pushed.
        """
        console.print()
        console.print("━" * 40)
        console.print(f"[bold]  Pushing: {calendar_name}[/bold]")
        console.print("━" * 40)

    def render_calendar_info(self, calendar_path: Path, event_count: int) -> None:
        """Render calendar info section.

        Args:
            calendar_path: Path to the calendar file.
            event_count: Number of events in the calendar.
        """
        console.print(f"\nCalendar: {calendar_path.resolve()}")
        console.print(f"  {event_count} events")

    def render_remote_warning(self) -> None:
        """Render warning when no remote is configured."""
        console.print(
            f"\n{typer.style('⚠', fg=typer.colors.YELLOW, bold=True)} No remote URL configured"
        )
        console.print("  Calendar will be committed locally but not pushed.")
        console.print(
            "  Run 'calendar-sync git-setup' to configure a remote repository."
        )
        console.print()

    def render_step_start(self, message: str) -> None:
        """Render start of a step (without newline).

        Args:
            message: Step description.
        """
        print(f"  {message}...", end=" ", flush=True)

    def render_step_done(self) -> None:
        """Render step completion."""
        print(typer.style("done", fg=typer.colors.GREEN))

    def render_step_failed(self) -> None:
        """Render step failure."""
        print(typer.style("failed", fg=typer.colors.RED))

    def render_success(self) -> None:
        """Render overall success message."""
        console.print(f"\n[bold green]✓[/bold green] Calendar pushed successfully")

    def render_subscription_urls(self, urls: list[str]) -> None:
        """Render subscription URLs.

        Args:
            urls: List of subscription URLs to display.
        """
        if urls:
            console.print("\nSubscription URLs:")
            for url in urls:
                console.print(f"  [cyan]{url}[/cyan]")
        else:
            console.print("\n  (Subscription URLs not available without remote)")


def push_calendar(
    git_service: GitService,
    calendar_name: str,
    calendar_path: Path,
    event_count: int,
    remote_url: str | None,
    show_header: bool = True,
) -> bool:
    """Execute push operation with expressive output.

    This is a shared function used by both the push command and sync -p
    to ensure consistent, expressive output for git push operations.

    Args:
        git_service: GitService instance for git operations.
        calendar_name: Name of the calendar to push.
        calendar_path: Path to the calendar file.
        event_count: Number of events in the calendar.
        remote_url: Remote URL if configured, None otherwise.
        show_header: Whether to show the push header (default True).
            Set to False when called from sync where context is clear.

    Returns:
        True if push succeeded, False otherwise.

    Raises:
        typer.Exit: On fatal errors with exit code 1.
    """
    renderer = PushRenderer()

    # Header (optional)
    if show_header:
        renderer.render_header(calendar_name)
        renderer.render_calendar_info(calendar_path, event_count)

    # Check remote configuration
    if not remote_url:
        renderer.render_remote_warning()

    # Push steps
    console.print("\nPushing...")

    try:
        # Step 1: Commit locally
        renderer.render_step_start("Staging and committing changes")
        git_service.commit_calendar_locally(calendar_name)
        renderer.render_step_done()

        # Step 2: Push to remote (only if remote is configured)
        if remote_url:
            renderer.render_step_start("Pushing to remote")
            git_service._push_changes()
            renderer.render_step_done()

        # Success message
        renderer.render_success()

        # Subscription URLs
        if remote_url:
            url_generator = SubscriptionUrlGenerator(
                git_service.repo_root, git_service.remote_url
            )
            urls = url_generator.generate_subscription_urls(
                calendar_name, calendar_path, "ics"
            )
            renderer.render_subscription_urls(urls)
        else:
            renderer.render_subscription_urls([])

        return True

    except (GitError, GitCommandError) as e:
        renderer.render_step_failed()
        console.print(f"\n[bold red]✗[/bold red] Git operation failed: {e}")
        return False
