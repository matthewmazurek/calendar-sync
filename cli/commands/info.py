"""Show calendar metadata: settings, ingestion info, git history, and subscription URL."""

import logging

import typer
from rich.table import Table
from typing_extensions import Annotated

from app.storage.subscription_url_generator import SubscriptionUrlGenerator
from cli.context import get_context
from cli.display import console, format_datetime, format_file_size, format_path

logger = logging.getLogger(__name__)


def info(
    name: Annotated[
        str,
        typer.Argument(help="Calendar name"),
    ],
) -> None:
    """Show calendar metadata: settings, ingestion info, git history, and subscription URL.

    Use 'stats' instead to analyze event data (counts by type, coverage metrics).
    """
    ctx = get_context()
    repository = ctx.repository
    git_service = ctx.git_service

    # Get paths for this calendar
    paths = repository.paths(name)
    calendar_path = paths.export("ics")

    # Load settings (config.json)
    settings = repository.load_settings(name)
    if settings is None:
        console.print(f"\n[red]Calendar '{name}' not found[/red]")
        raise typer.Exit(1)

    # Load calendar (data.json) - may not exist if never ingested
    calendar = repository.load_calendar(name)

    # ─────────────────────────────────────────────────────────────────────────
    # Header
    # ─────────────────────────────────────────────────────────────────────────
    display_name = settings.name or name
    console.print()
    console.print("━" * 60)
    console.print(f"[bold]  Calendar: {name}[/bold]")
    console.print("━" * 60)

    # ─────────────────────────────────────────────────────────────────────────
    # Calendar Info (from config.json)
    # ─────────────────────────────────────────────────────────────────────────
    console.print("\n[bold cyan]Calendar Info[/bold cyan]")

    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("Label", style="dim", width=18)
    info_table.add_column("Value")

    info_table.add_row("ID", f"[cyan]{name}[/cyan]")
    if settings.name:
        info_table.add_row("Display name", settings.name)
    if settings.description:
        info_table.add_row("Description", settings.description)
    if settings.template:
        info_table.add_row("Template", settings.template)
    info_table.add_row("Created", format_datetime(settings.created))
    info_table.add_row("Path", format_path(paths.directory))

    console.print(info_table)

    # ─────────────────────────────────────────────────────────────────────────
    # Ingestion Info (from data.json metadata)
    # ─────────────────────────────────────────────────────────────────────────
    console.print("\n[bold cyan]Ingestion Info[/bold cyan]")

    if calendar:
        ingest_table = Table(show_header=False, box=None, padding=(0, 2))
        ingest_table.add_column("Label", style="dim", width=18)
        ingest_table.add_column("Value")

        # Calculate date range from events
        if calendar.events:
            dates = [event.date for event in calendar.events]
            min_date = min(dates)
            max_date = max(dates)
            date_range = f"{min_date} to {max_date}"
            event_count = f"{len(calendar.events):,} events"
        else:
            date_range = "no events"
            event_count = "0 events"

        ingest_table.add_row("Events", event_count)
        ingest_table.add_row("Date range", date_range)
        if calendar.source_revised_at:
            ingest_table.add_row(
                "Source revised", format_datetime(calendar.source_revised_at)
            )
        ingest_table.add_row("Last updated", format_datetime(calendar.last_updated))
        if calendar.template_name:
            template_info = calendar.template_name
            if calendar.template_version:
                template_info += f" v{calendar.template_version}"
            ingest_table.add_row("Applied template", template_info)

        # Data file (canonical storage)
        if paths.data.exists():
            data_size = paths.data.stat().st_size
            ingest_table.add_row(
                "Data file",
                f"{format_path(paths.data)} [dim]({format_file_size(data_size)})[/dim]",
            )

        console.print(ingest_table)
    else:
        console.print("  [dim]No data ingested yet[/dim]")

    # ─────────────────────────────────────────────────────────────────────────
    # Git Info
    # ─────────────────────────────────────────────────────────────────────────
    console.print("\n[bold cyan]Git Info[/bold cyan]")

    versions = repository.list_calendar_versions(name)
    commit_count = len(versions)

    if commit_count > 0:
        git_table = Table(show_header=False, box=None, padding=(0, 2))
        git_table.add_column("Label", style="dim", width=18)
        git_table.add_column("Value")

        git_table.add_row("Commits", str(commit_count))

        # Get latest commit info
        latest_commit_hash, latest_commit_date, latest_commit_message = versions[0]

        # Get current version (what's in working directory)
        current_commit_hash = None
        if paths.data.exists():
            current_commit_hash = git_service.get_current_commit_hash(paths.data)

        # Show current version
        if current_commit_hash:
            current_commit_date = None
            for commit_hash, commit_date, _ in versions:
                if commit_hash == current_commit_hash:
                    current_commit_date = commit_date
                    break

            if current_commit_date:
                current_str = f"[cyan]{current_commit_hash[:7]}[/cyan] ({format_datetime(current_commit_date, include_relative=False)})"
            else:
                current_str = f"[cyan]{current_commit_hash[:7]}[/cyan]"
        else:
            current_str = "[yellow]uncommitted changes[/yellow]"

        git_table.add_row("Current", current_str)
        git_table.add_row(
            "Latest",
            f"[cyan]{latest_commit_hash[:7]}[/cyan] ({format_datetime(latest_commit_date, include_relative=False)})",
        )

        # Show remote info
        remote_url = git_service.get_remote_url()
        if remote_url:
            git_table.add_row("Remote", f"[dim]{remote_url}[/dim]")
        else:
            git_table.add_row("Remote", "[dim]not configured[/dim]")

        console.print(git_table)
    else:
        console.print("  [dim]Not tracked in git[/dim]")

    # ─────────────────────────────────────────────────────────────────────────
    # Exported Files
    # ─────────────────────────────────────────────────────────────────────────
    console.print("\n[bold cyan]Exported Files[/bold cyan]")

    ics_path = paths.export("ics")
    if ics_path.exists():
        export_table = Table(show_header=False, box=None, padding=(0, 2))
        export_table.add_column("Label", style="dim", width=18)
        export_table.add_column("Value")

        ics_size = ics_path.stat().st_size
        export_table.add_row(
            "calendar.ics",
            f"{format_path(ics_path)} [dim]({format_file_size(ics_size)})[/dim]",
        )
        console.print(export_table)
    else:
        console.print("  [dim]No exports yet[/dim]")

    # ─────────────────────────────────────────────────────────────────────────
    # Subscription Info
    # ─────────────────────────────────────────────────────────────────────────
    console.print("\n[bold cyan]Subscription Info[/bold cyan]")

    if commit_count > 0 and calendar_path:
        url_generator = SubscriptionUrlGenerator(
            git_service.repo_root, git_service.remote_url
        )
        subscription_urls = url_generator.generate_subscription_urls(
            name, calendar_path, "ics"
        )
        if subscription_urls:
            sub_table = Table(show_header=False, box=None, padding=(0, 2))
            sub_table.add_column("Label", style="dim", width=18)
            sub_table.add_column("Value")
            sub_table.add_row(
                "URL", f"[blue underline]{subscription_urls[0]}[/blue underline]"
            )
            console.print(sub_table)
        else:
            console.print("  [dim]Not available (no remote configured)[/dim]")
    else:
        console.print("  [dim]Not available (not published)[/dim]")

    console.print()  # Final newline
