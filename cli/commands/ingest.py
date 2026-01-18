"""Ingest calendar data file and save as canonical JSON."""

import logging
import sys
from datetime import date
from enum import Enum
from pathlib import Path

import typer
from typing_extensions import Annotated

from app.exceptions import IngestionError, InvalidYearError, UnsupportedFormatError
from app.ingestion.service import IngestionService
from app.models.ingestion import IngestionContext
from app.models.template_loader import get_template
from app.processing.calendar_manager import CalendarManager, get_default_strategy_for_source
from app.processing.merge_strategies import (
    Add,
    MergeStrategy,
    ReplaceByRange,
    ReplaceByYear,
    UpsertById,
)
from cli.commands.diff import display_diff
from cli.context import get_context
from cli.display import SummaryRenderer, console
from cli.utils import confirm_or_exit

logger = logging.getLogger(__name__)


# Strategy option choices as Enum (Typer doesn't support Literal types)
class StrategyChoice(str, Enum):
    replace_year = "replace-year"
    upsert = "upsert"
    add = "add"


def parse_date(date_str: str) -> date:
    """Parse a date string in YYYY-MM-DD format."""
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise typer.BadParameter(f"Invalid date format: {date_str}. Use YYYY-MM-DD.")


def ingest_command(
    calendar_name: Annotated[
        str,
        typer.Argument(help="Calendar name to create or update"),
    ],
    calendar_data_file: Annotated[
        str,
        typer.Argument(help="Path to input calendar file (DOCX, ICS, or JSON)"),
    ],
    year: Annotated[
        int | None,
        typer.Option(
            "--year", "-y", help="Year to replace (for ReplaceByYear strategy)"
        ),
    ] = None,
    strategy: Annotated[
        StrategyChoice | None,
        typer.Option(
            "--strategy", "-s",
            help="Merge strategy: replace-year (default for Word), upsert (default for ICS), add (default for JSON)"
        ),
    ] = None,
    replace_from: Annotated[
        str | None,
        typer.Option(
            "--replace-from",
            help="Start date for ReplaceByRange (YYYY-MM-DD). Requires --replace-to."
        ),
    ] = None,
    replace_to: Annotated[
        str | None,
        typer.Option(
            "--replace-to",
            help="End date for ReplaceByRange (YYYY-MM-DD). Requires --replace-from."
        ),
    ] = None,
    template_name: Annotated[
        str | None,
        typer.Option(
            "--template", "-t", help="Template name to use (overrides config)"
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Skip confirmation prompt and save directly"
        ),
    ] = False,
) -> None:
    """Ingest calendar data file and save as canonical JSON.

    This command reads a source file (Word, ICS, or JSON), processes it
    using the template, and saves to data.json.

    MERGE STRATEGIES:
    
    - replace-year: Replace all events for a specific year (default for Word)
    - upsert: Update existing events by UID, add new ones (default for ICS)
    - add: Simply add new events without removing any (default for JSON)
    
    You can also specify a custom date range with --replace-from and --replace-to.

    By default, shows a preview and prompts for confirmation before saving.
    Use --force to skip the confirmation and save directly.

    Note: This only saves the JSON file. Use 'export' to generate ICS,
    and 'commit' to commit changes to git.
    """
    ctx = get_context()
    config = ctx.config
    repository = ctx.repository
    reader_registry = ctx.reader_registry
    renderer = SummaryRenderer()

    # Validate date range options
    if (replace_from is None) != (replace_to is None):
        console.print("[red]Error: --replace-from and --replace-to must be used together[/red]")
        sys.exit(1)

    # ─────────────────────────────────────────────────────────────────────────
    # Load template (fallback: CLI arg → calendar config → global config)
    # ─────────────────────────────────────────────────────────────────────────
    calendar_settings = repository.load_settings(calendar_name)
    calendar_template = calendar_settings.template if calendar_settings else None
    effective_template_name = template_name or calendar_template or config.default_template
    template = get_template(effective_template_name, config.template_dir)
    logger.info(f"Using template: {template.name} (version {template.version})")
    if template.extends:
        logger.info(f"Template extends: {template.extends}")

    # ─────────────────────────────────────────────────────────────────────────
    # Auto-create calendar if it doesn't exist
    # ─────────────────────────────────────────────────────────────────────────
    if not repository.calendar_exists(calendar_name):
        logger.info(f"Creating new calendar: {calendar_name}")
        repository.create_calendar(
            calendar_id=calendar_name,
            template=effective_template_name,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Ingest source file
    # ─────────────────────────────────────────────────────────────────────────
    input_path = Path(calendar_data_file).expanduser().resolve()
    ingestion_service = IngestionService(reader_registry)

    try:
        ingestion_result = ingestion_service.ingest(input_path, template)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except UnsupportedFormatError as e:
        logger.error(str(e))
        sys.exit(1)
    except IngestionError as e:
        logger.error(f"Failed to read calendar file: {e}")
        sys.exit(1)
    except InvalidYearError as e:
        logger.error(f"Year validation error: {e}")
        sys.exit(1)

    # Check if calendar exists
    existing = repository.load_calendar(calendar_name)
    is_new = existing is None

    ingestion_ctx = IngestionContext(
        input_path=input_path,
        ingestion_result=ingestion_result,
        existing_calendar=existing,
        is_new=is_new,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Determine merge strategy
    # ─────────────────────────────────────────────────────────────────────────
    merge_strategy: MergeStrategy | None = None
    
    if not is_new:
        # Build merge strategy from options
        if replace_from and replace_to:
            # Explicit date range
            merge_strategy = ReplaceByRange(
                start_date=parse_date(replace_from),
                end_date=parse_date(replace_to),
            )
        elif strategy:
            # Explicit strategy choice
            if strategy == "replace-year":
                if year is None:
                    # Try to infer from events
                    from app.processing.merge_strategies import infer_year
                    inferred = infer_year(ingestion_result.raw.events)
                    if inferred is None:
                        console.print(
                            "[red]Error: Cannot infer year from multi-year source. "
                            "Use --year to specify.[/red]"
                        )
                        sys.exit(1)
                    year = inferred
                merge_strategy = ReplaceByYear(year)
            elif strategy == "upsert":
                merge_strategy = UpsertById()
            elif strategy == "add":
                merge_strategy = Add()
        elif year:
            # Year specified without strategy - use ReplaceByYear
            merge_strategy = ReplaceByYear(year)
        else:
            # Use default strategy for source type
            try:
                merge_strategy = get_default_strategy_for_source(
                    input_path.suffix,
                    ingestion_result.raw.events,
                    year,
                )
            except InvalidYearError as e:
                logger.error(f"Year validation error: {e}")
                sys.exit(1)

    # ─────────────────────────────────────────────────────────────────────────
    # Output: Header
    # ─────────────────────────────────────────────────────────────────────────
    action = "Ingesting (new)" if ingestion_ctx.is_new else "Ingesting (update)"
    renderer.render_header(action, calendar_name)

    # Show merge strategy
    if merge_strategy:
        strategy_desc = _describe_strategy(merge_strategy)
        console.print(f"  Merge strategy: [cyan]{strategy_desc}[/cyan]")

    # ─────────────────────────────────────────────────────────────────────────
    # Output: Source info
    # ─────────────────────────────────────────────────────────────────────────
    renderer.render_source_info(
        ingestion_ctx.input_path,
        ingestion_ctx.ingestion_result.summary,
        template,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Process calendar
    # ─────────────────────────────────────────────────────────────────────────
    manager = CalendarManager(repository)

    try:
        processing_result = manager.create_or_update(
            calendar_name,
            ingestion_ctx.ingestion_result.raw,
            ingestion_ctx.is_new,
            template,
            merge_strategy,
            year,
        )
    except InvalidYearError as e:
        logger.error(f"Year validation error: {e}")
        sys.exit(1)

    # ─────────────────────────────────────────────────────────────────────────
    # Output: Processing summary and stats
    # ─────────────────────────────────────────────────────────────────────────
    renderer.render_processing_summary(processing_result.processing_summary)
    renderer.render_stats(ingestion_ctx.ingestion_result.summary.model_dump())

    # ─────────────────────────────────────────────────────────────────────────
    # Output: Diff
    # ─────────────────────────────────────────────────────────────────────────
    if ingestion_ctx.is_new:
        display_diff(
            None, processing_result.calendar.events, "empty", "new", compact=True
        )
    else:
        display_diff(
            ingestion_ctx.existing_calendar.events if ingestion_ctx.existing_calendar else None,
            processing_result.calendar.events,
            "previous",
            "updated",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Confirmation and Save
    # ─────────────────────────────────────────────────────────────────────────
    confirm_or_exit("Save calendar JSON?", force)

    # Save calendar JSON only (no ICS export, no commit)
    json_path = repository.save_json(processing_result.calendar)

    # Success message
    if ingestion_ctx.is_new:
        renderer.render_success("Calendar ingested (new)", json_path)
    else:
        year_msg = f" (year {processing_result.year})" if processing_result.year else ""
        renderer.render_success(f"Calendar ingested{year_msg}", json_path)

    console.print(f"\n[bold]Next steps:[/bold]")
    console.print(f"  • Run 'export {calendar_name}' to generate ICS")
    console.print(f"  • Run 'commit {calendar_name}' to commit to git")


def _describe_strategy(strategy: MergeStrategy) -> str:
    """Get a human-readable description of a merge strategy."""
    match strategy:
        case ReplaceByYear(year=y):
            return f"Replace year {y}"
        case ReplaceByRange(start_date=s, end_date=e):
            return f"Replace range {s} to {e}"
        case UpsertById():
            return "Upsert by ID"
        case Add():
            return "Add events"
    return str(strategy)


# Alias for CLI registration
ingest = ingest_command
