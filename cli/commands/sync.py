"""Sync calendar data file and create or update calendar."""

import logging
import sys
from pathlib import Path

from app.config import CalendarConfig
from app.exceptions import (
    CalendarNotFoundError,
    IngestionError,
    InvalidYearError,
    UnsupportedFormatError,
)
from app.models.template_loader import get_template
from app.processing.calendar_manager import CalendarManager
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage
from app.storage.git_service import GitService
from cli.setup import setup_reader_registry, setup_writer
from cli.utils import format_complete_summary

logger = logging.getLogger(__name__)


def sync_command(
    calendar_data_file: str,
    calendar_name: str,
    year: int | None = None,
    format: str = "ics",
    publish: bool = False,
) -> None:
    """
    Sync calendar data file and create or update calendar.

    Args:
        calendar_data_file: Path to input calendar file
        calendar_name: Name of calendar to create or update
        year: Optional year to replace (for composition)
        format: Output format (ics or json)
        publish: If True, commit and push calendar changes to git
    """
    config = CalendarConfig.from_env()
    storage = CalendarStorage(config)
    reader_registry = setup_reader_registry()
    git_service = GitService(
        config.calendar_dir,
        remote_url=config.calendar_git_remote_url,
    )
    repository = CalendarRepository(
        config.calendar_dir, storage, git_service, reader_registry
    )

    # Load template if configured
    template = get_template(config.default_template, config.template_dir)
    if template:
        logger.info(f"Using template: {template.name} (version {template.version})")
        if template.extends:
            logger.info(f"Template extends: {template.extends}")
    else:
        logger.info(
            "No template configured - events will be processed without template rules"
        )

    # Read input file
    input_path = Path(calendar_data_file).expanduser()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {calendar_data_file}")

    try:
        reader = reader_registry.get_reader(input_path)
        file_format = input_path.suffix.lower()
        reader_name = reader.__class__.__name__
        logger.info(
            f"Reading calendar file: {input_path} (format: {file_format}, reader: {reader_name})"
        )
    except UnsupportedFormatError as e:
        logger.error(str(e))
        sys.exit(1)

    try:
        # Pass template to WordReader if it's a WordReader
        from app.ingestion.word_reader import WordReader

        if isinstance(reader, WordReader) and template:
            source_calendar = reader.read(input_path, template)
        else:
            source_calendar = reader.read(input_path)

        # Calculate date range
        if source_calendar.events:
            dates = [event.date for event in source_calendar.events]
            min_date = min(dates)
            max_date = max(dates)
            date_range = f"{min_date} to {max_date}"
        else:
            date_range = "no events"

        # Collect ingestion summary data (will be printed at the end)
        ingestion_summary = {
            "format": file_format,
            "reader_name": reader_name,
            "events": len(source_calendar.events),
            "date_range": date_range,
            "year": source_calendar.year,
            "revised_date": source_calendar.revised_date,
        }
        logger.info(f"Ingested {len(source_calendar.events)} events from {input_path}")
    except IngestionError as e:
        logger.error(f"Failed to read calendar file: {e}")
        sys.exit(1)
    except InvalidYearError as e:
        logger.error(f"Year validation error: {e}")
        sys.exit(1)

    # Create calendar manager
    manager = CalendarManager(repository)

    # Check if calendar exists
    existing = repository.load_calendar(calendar_name, format)

    if existing is None:
        # Creating new calendar - allow multi-year calendars
        action_message = f"Creating new calendar '{calendar_name}'"
        logger.info(action_message)
        try:
            result, processing_summary = manager.create_calendar_from_source(
                source_calendar, calendar_name, template
            )
        except InvalidYearError as e:
            logger.error(f"Year validation error: {e}")
            sys.exit(1)

        # Save calendar
        writer = setup_writer(format)
        filepath = repository.save_calendar(result.calendar, result.metadata, writer)
        logger.info(f"Calendar created: {filepath}")

        # Publish to git if requested
        if publish:
            git_service.publish_calendar(calendar_name, filepath, format)
            logger.info("Calendar published to git")

        # Print complete summary at the end
        format_complete_summary(
            ingestion_summary=ingestion_summary,
            processing_summary=processing_summary,
            action_message=action_message,
            filepath=filepath,
            published=publish,
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

        action_message = f"Updating calendar '{calendar_name}' for year {year}"
        logger.info(action_message)
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

        # Save updated calendar
        writer = setup_writer(format)
        filepath = repository.save_calendar(result.calendar, result.metadata, writer)
        logger.info(f"Calendar updated: {filepath}")

        # Publish to git if requested
        if publish:
            git_service.publish_calendar(calendar_name, filepath, format)
            logger.info("Calendar published to git")

        # Print complete summary at the end
        format_complete_summary(
            ingestion_summary=ingestion_summary,
            processing_summary=processing_summary,
            action_message=action_message,
            filepath=filepath,
            published=publish,
        )
