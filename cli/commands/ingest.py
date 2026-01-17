"""Ingest calendar data file and save as canonical JSON."""

import logging
import sys
from pathlib import Path

import typer
from typing_extensions import Annotated

from app.exceptions import IngestionError, InvalidYearError, UnsupportedFormatError
from app.ingestion.service import IngestionService
from app.models.ingestion import IngestionContext
from app.models.template_loader import get_template
from app.processing.calendar_manager import CalendarManager
from cli.commands.diff import display_diff
from cli.context import get_context
from cli.display import SummaryRenderer, console
from cli.utils import confirm_or_exit

logger = logging.getLogger(__name__)


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
            "--year", "-y", help="Year to replace when updating existing calendar"
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
    using the template, and saves to calendar_data.json.

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

    # ─────────────────────────────────────────────────────────────────────────
    # Load template
    # ─────────────────────────────────────────────────────────────────────────
    effective_template_name = template_name or config.default_template
    template = get_template(effective_template_name, config.template_dir)
    logger.info(f"Using template: {template.name} (version {template.version})")
    if template.extends:
        logger.info(f"Template extends: {template.extends}")

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
    existing_calendar = existing.calendar if existing else None
    is_new = existing is None

    ingestion_ctx = IngestionContext(
        input_path=input_path,
        ingestion_result=ingestion_result,
        existing_calendar=existing_calendar,
        is_new=is_new,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Output: Header
    # ─────────────────────────────────────────────────────────────────────────
    action = "Ingesting (new)" if ingestion_ctx.is_new else "Ingesting (update)"
    renderer.render_header(action, calendar_name)

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
            ingestion_ctx.ingestion_result.calendar,
            ingestion_ctx.is_new,
            template,
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
            None, processing_result.result.calendar, "empty", "new", compact=True
        )
    else:
        display_diff(
            ingestion_ctx.existing_calendar,
            processing_result.result.calendar,
            "previous",
            "updated",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Confirmation and Save
    # ─────────────────────────────────────────────────────────────────────────
    confirm_or_exit("Save calendar JSON?", force)

    # Save calendar JSON only (no ICS export, no commit)
    json_path = repository.save_json(
        processing_result.result.calendar,
        processing_result.result.metadata,
    )

    # Success message
    if ingestion_ctx.is_new:
        renderer.render_success("Calendar ingested (new)", json_path)
    else:
        renderer.render_success(f"Calendar ingested (year {processing_result.year})", json_path)

    console.print(f"\n[bold]Next steps:[/bold]")
    console.print(f"  • Run 'export {calendar_name}' to generate ICS")
    console.print(f"  • Run 'commit {calendar_name}' to commit to git")


# Alias for CLI registration
ingest = ingest_command
