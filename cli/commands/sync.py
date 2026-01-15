"""Sync calendar data file and create or update calendar."""

import logging
import sys
from pathlib import Path

import typer
from typing_extensions import Annotated

from app.exceptions import (
    CalendarNotFoundError,
    IngestionError,
    InvalidYearError,
    UnsupportedFormatError,
)
from app.models.template_loader import get_template
from app.processing.calendar_manager import CalendarManager
from cli.commands.diff import display_diff
from cli.context import get_context

logger = logging.getLogger(__name__)


def _format_processing_summary(processing_summary: dict) -> None:
    """Format processing summary with arrow notation for collapsed events."""
    if not processing_summary:
        return

    input_counts = processing_summary.get("input_counts", {})
    output_counts = processing_summary.get("output_counts", {})
    input_total = processing_summary.get("input_total", 0)
    output_total = processing_summary.get("output_total", 0)

    if not input_counts:
        return

    print("\nProcessing:")

    # Format each event type
    for event_type, count in sorted(input_counts.items()):
        output_count = output_counts.get(event_type, 0)
        if output_count != count:
            print(f"  {event_type}: {count} → {output_count}")
        else:
            print(f"  {event_type}: {count}")

    # Total with separator
    print("  " + "─" * 30)
    if output_total != input_total:
        print(f"  Total: {input_total} → {output_total}")
    else:
        print(f"  Total: {input_total}")


def _format_stats(ingestion_summary: dict) -> None:
    """Format statistics in a compact single line."""
    parts = []

    total_halfdays = ingestion_summary.get("total_halfdays")
    weekly_coverage_year = ingestion_summary.get("weekly_coverage_year")

    if total_halfdays is not None:
        parts.append(f"{total_halfdays} half-days")
    if weekly_coverage_year is not None:
        parts.append(f"{weekly_coverage_year:.1f}/week coverage")

    if parts:
        print(f"\nStats: {' · '.join(parts)}")


def sync_command(
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
            "--year", "-y", help="Year to replace when updating existing calendar"
        ),
    ] = None,
    format: Annotated[
        str | None,
        typer.Option("--format", "-o", help="Output format: ics or json"),
    ] = None,
    template_name: Annotated[
        str | None,
        typer.Option(
            "--template", "-t", help="Template name to use (overrides config)"
        ),
    ] = None,
    publish: Annotated[
        bool,
        typer.Option("--publish", "-p", help="Commit and push calendar changes to git"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Sync calendar data file and create or update calendar."""
    ctx = get_context()
    config = ctx.config
    repository = ctx.repository
    git_service = ctx.git_service
    reader_registry = ctx.reader_registry

    # Read input file
    input_path = Path(calendar_data_file).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {calendar_data_file}")

    # Use config default format if not specified
    if format is None:
        format = config.default_format

    # Load template (use override or fallback to config)
    effective_template_name = template_name or config.default_template
    template = get_template(effective_template_name, config.template_dir)
    logger.info(f"Using template: {template.name} (version {template.version})")
    if template.extends:
        logger.info(f"Template extends: {template.extends}")

    try:
        reader = reader_registry.get_reader(input_path)
        reader_name = reader.__class__.__name__
        logger.info(
            f"Reading calendar file: {input_path} (format: {input_path.suffix}, reader: {reader_name})"
        )
    except UnsupportedFormatError as e:
        logger.error(str(e))
        sys.exit(1)

    # Check if calendar exists (for diff later)
    existing = repository.load_calendar(calendar_name, format)
    existing_calendar = existing.calendar if existing else None

    try:
        # Pass template to WordReader if it's a WordReader
        from app.ingestion.word_reader import WordReader

        if isinstance(reader, WordReader):
            ingestion_result = reader.read(input_path, template)
        else:
            ingestion_result = reader.read(input_path)

        source_calendar = ingestion_result.calendar
        ingestion_summary = ingestion_result.summary

    except IngestionError as e:
        logger.error(f"Failed to read calendar file: {e}")
        sys.exit(1)
    except InvalidYearError as e:
        logger.error(f"Year validation error: {e}")
        sys.exit(1)

    # ─────────────────────────────────────────────────────────────────────────
    # Output: Header
    # ─────────────────────────────────────────────────────────────────────────
    is_new = existing is None
    action = "Creating" if is_new else "Updating"
    print(f"\n{'━' * 40}")
    print(typer.style(f"  {action}: {calendar_name}", bold=True))
    print(f"{'━' * 40}")

    # ─────────────────────────────────────────────────────────────────────────
    # Output: Source info (condensed)
    # ─────────────────────────────────────────────────────────────────────────
    date_range = ingestion_summary.date_range
    print(f"\nSource: {input_path}")
    source_details = [f"{ingestion_summary.events} events", date_range]
    if ingestion_summary.revised_date:
        source_details.append(f"revised {ingestion_summary.revised_date}")
    print(f"  {' · '.join(source_details)}")

    # Template info
    template_info = f"Template: {template.name}"
    if template.extends:
        template_info += f" (extends {template.extends})"
    print(f"  {template_info}")

    logger.info(f"Ingested {len(source_calendar.events)} events from {input_path}")

    # Create calendar manager
    manager = CalendarManager(repository)

    # ─────────────────────────────────────────────────────────────────────────
    # Process calendar (preview only - don't save yet)
    # ─────────────────────────────────────────────────────────────────────────
    if is_new:
        # Creating new calendar - allow multi-year calendars
        try:
            result, processing_summary = manager.create_calendar_from_source(
                source_calendar, calendar_name, template
            )
        except InvalidYearError as e:
            logger.error(f"Year validation error: {e}")
            sys.exit(1)

        # Processing summary
        _format_processing_summary(processing_summary)

        # Stats
        _format_stats(ingestion_summary.model_dump())

        # Show diff (everything is new)
        display_diff(None, result.calendar, "empty", "new", compact=True)

        # Interactive confirmation unless --force is set
        if not force:
            typer.echo()
            if not typer.confirm("Continue?"):
                typer.echo("Sync cancelled.")
                raise typer.Exit(0)

        # Save calendar
        writer = ctx.get_writer(format)
        filepath = repository.save_calendar(result.calendar, result.metadata, writer)
        filepath_abs = Path(filepath).resolve()

        # Success message with clickable path
        print(
            f"\n{typer.style('✓', fg=typer.colors.GREEN, bold=True)} Calendar created"
        )
        print(f"  {filepath_abs}")
        logger.info(f"Calendar created: {filepath}")

        # Publish to git if requested
        if publish:
            git_service.publish_calendar(calendar_name, filepath, format)
            print(
                f"{typer.style('✓', fg=typer.colors.GREEN, bold=True)} Published to git"
            )
    else:
        # Compose with existing calendar - requires year specification
        # Determine year if not specified
        if year is None:
            if source_calendar.year is None:
                years = {event.date.year for event in source_calendar.events}
                if len(years) != 1:
                    logger.error(
                        f"Source calendar contains events from multiple years: {years}. "
                        "Please specify --year option when updating an existing calendar."
                    )
                    sys.exit(1)
                year = years.pop()
            else:
                year = source_calendar.year

        try:
            result, processing_summary = manager.compose_calendar_with_source(
                calendar_name, source_calendar, year, repository, template
            )
        except CalendarNotFoundError as e:
            logger.error(f"Calendar not found: {e}")
            sys.exit(1)
        except InvalidYearError as e:
            logger.error(f"Year validation error: {e}")
            sys.exit(1)

        # Processing summary
        _format_processing_summary(processing_summary)

        # Stats
        _format_stats(ingestion_summary.model_dump())

        # Show diff between old and new calendar
        display_diff(existing_calendar, result.calendar, "previous", "updated")

        # Interactive confirmation unless --force is set
        if not force:
            typer.echo()
            if not typer.confirm("Continue?"):
                typer.echo("Sync cancelled.")
                raise typer.Exit(0)

        # Save updated calendar
        writer = ctx.get_writer(format)
        filepath = repository.save_calendar(result.calendar, result.metadata, writer)
        filepath_abs = Path(filepath).resolve()

        # Success message with clickable path
        print(
            f"\n{typer.style('✓', fg=typer.colors.GREEN, bold=True)} Calendar updated (year {year})"
        )
        print(f"  {filepath_abs}")
        logger.info(f"Calendar updated: {filepath}")

        # Publish to git if requested
        if publish:
            git_service.publish_calendar(calendar_name, filepath, format)
            print(
                f"{typer.style('✓', fg=typer.colors.GREEN, bold=True)} Published to git"
            )


# Alias for backwards compatibility with CLI registration
sync = sync_command
