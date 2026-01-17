"""Sync calendar data file and create or update calendar.

This command combines ingestion, export, and optional push into a single
workflow. It's equivalent to running: ingest → export → commit → push.
"""

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
from cli.display import SummaryRenderer
from cli.utils import confirm_or_exit

logger = logging.getLogger(__name__)


def sync_command(
    calendar_id: Annotated[
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
    push: Annotated[
        bool,
        typer.Option("--push", "-p", help="Commit and push calendar changes to git"),
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
    renderer = SummaryRenderer()

    # ─────────────────────────────────────────────────────────────────────────
    # Load template (fallback: CLI arg → calendar config → global config)
    # ─────────────────────────────────────────────────────────────────────────
    calendar_settings = repository.load_settings(calendar_id)
    calendar_template = calendar_settings.template if calendar_settings else None
    effective_template_name = (
        template_name or calendar_template or config.default_template
    )
    template = get_template(effective_template_name, config.template_dir)
    logger.info(f"Using template: {template.name} (version {template.version})")
    if template.extends:
        logger.info(f"Template extends: {template.extends}")

    # ─────────────────────────────────────────────────────────────────────────
    # Auto-create calendar if it doesn't exist
    # ─────────────────────────────────────────────────────────────────────────
    if not repository.calendar_exists(calendar_id):
        logger.info(f"Creating new calendar: {calendar_id}")
        repository.create_calendar(
            calendar_id=calendar_id,
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
    existing = repository.load_calendar(calendar_id)
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
    action = "Creating" if ingestion_ctx.is_new else "Updating"
    renderer.render_header(action, calendar_id)

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
            calendar_id,
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
    # Confirmation
    # ─────────────────────────────────────────────────────────────────────────
    confirm_or_exit("Continue?", force)

    # ─────────────────────────────────────────────────────────────────────────
    # Save: JSON + ICS export + local commit
    # ─────────────────────────────────────────────────────────────────────────
    filepath = repository.save_calendar(
        processing_result.result.calendar,
        processing_result.result.metadata,
        template=template,
    )

    # Success message
    if ingestion_ctx.is_new:
        renderer.render_success("Calendar created", filepath)
    else:
        renderer.render_success(
            f"Calendar updated (year {processing_result.year})", filepath
        )

    logger.info(f"Calendar saved: {filepath}")

    # ─────────────────────────────────────────────────────────────────────────
    # Publish to git (optional)
    # ─────────────────────────────────────────────────────────────────────────
    if push:
        git_service.publish_calendar(calendar_id, filepath)
        renderer.render_success("Pushed to git")


# Alias for backwards compatibility with CLI registration
sync = sync_command
