"""Calendar manager with simplified create/compose operations."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from app.exceptions import CalendarNotFoundError, InvalidYearError
from app.models.calendar import Calendar
from app.models.metadata import CalendarMetadata, CalendarWithMetadata
from app.models.template import CalendarTemplate
from app.processing.calendar_merger import replace_year_in_calendar
from app.processing.calendar_processor import CalendarProcessor

logger = logging.getLogger(__name__)


class CalendarRepository(Protocol):
    """Protocol for calendar repository."""

    def load_calendar(self, name: str) -> CalendarWithMetadata | None:
        """Load calendar by name."""
        ...

    def save_calendar(
        self, calendar: Calendar, metadata: CalendarMetadata
    ) -> Path:
        """Save calendar with metadata."""
        ...


@dataclass
class ProcessingResult:
    """Result from calendar processing operations."""

    result: CalendarWithMetadata
    processing_summary: dict
    year: int | None  # Year being updated (None for new calendars)


class CalendarManager:
    """High-level calendar management operations."""

    def __init__(self, repository: CalendarRepository):
        """Initialize with repository (dependency injection)."""
        self.repository = repository
        self.processor = CalendarProcessor()

    def create_calendar_from_source(
        self,
        source_data: Calendar,
        calendar_name: str,
        template: CalendarTemplate | None = None,
    ) -> tuple[CalendarWithMetadata, dict]:
        """
        Create new calendar from source file (replaces all events).

        Args:
            source_data: Source calendar data
            calendar_name: Name for the calendar
            template: Optional template configuration

        Returns:
            Tuple of (CalendarWithMetadata, processing_summary_dict)
        """
        # Allow multi-year calendars when creating new calendars
        # (Calendar model supports year=None for multi-year calendars)

        # Process events
        processed_calendar, processing_summary = self.processor.process(
            source_data, template
        )

        # Create metadata
        now = datetime.now()
        metadata = CalendarMetadata(
            name=calendar_name,
            source=None,
            created=now,
            last_updated=now,
            composed_from=None,
            source_revised_at=source_data.revised_date,  # Extract from Calendar
            template_name=template.name if template else None,
            template_version=template.version if template else None,
        )

        return (
            CalendarWithMetadata(calendar=processed_calendar, metadata=metadata),
            processing_summary,
        )

    def compose_calendar_with_source(
        self,
        calendar_name: str,
        source_data: Calendar,
        year: int,
        repository: CalendarRepository,
        template: CalendarTemplate | None = None,
    ) -> tuple[CalendarWithMetadata, dict]:
        """
        Compose existing calendar with source file (replaces all events in specified year).

        Args:
            calendar_name: Name of existing calendar
            source_data: Source calendar data
            year: Year to replace
            repository: Calendar repository (dependency injection)
            template: Optional template configuration

        Returns:
            Tuple of (CalendarWithMetadata, processing_summary_dict)
        """
        # Load existing calendar
        existing_with_metadata = repository.load_calendar(calendar_name)
        if existing_with_metadata is None:
            raise CalendarNotFoundError(f"Calendar '{calendar_name}' not found")

        existing = existing_with_metadata.calendar
        existing_metadata = existing_with_metadata.metadata

        # Validate source calendar contains events from single year matching year parameter
        if source_data.year is not None and source_data.year != year:
            raise InvalidYearError(
                f"Source calendar year ({source_data.year}) does not match specified year ({year})"
            )

        for event in source_data.events:
            if event.date.year != year:
                raise InvalidYearError(
                    f"Source calendar contains event from year {event.date.year}, "
                    f"but specified year is {year}"
                )

        # Process source events
        processed_source, processing_summary = self.processor.process(
            source_data, template
        )

        # Compose with source file (replaces all events in specified year)
        merged_calendar = replace_year_in_calendar(processed_source, existing, year)

        # Update metadata
        updated_metadata = CalendarMetadata(
            name=existing_metadata.name,
            source=existing_metadata.source,
            created=existing_metadata.created,
            last_updated=datetime.now(),
            composed_from=existing_metadata.composed_from,
            source_revised_at=(
                source_data.revised_date
                if source_data.revised_date
                else existing_metadata.source_revised_at
            ),
            template_name=template.name if template else existing_metadata.template_name,
            template_version=template.version if template else existing_metadata.template_version,
        )

        return (
            CalendarWithMetadata(calendar=merged_calendar, metadata=updated_metadata),
            processing_summary,
        )

    def create_or_update(
        self,
        calendar_name: str,
        source_calendar: Calendar,
        is_new: bool,
        template: CalendarTemplate | None = None,
        year: int | None = None,
    ) -> ProcessingResult:
        """
        Create new calendar or update existing one.

        This is a higher-level method that handles both create and update cases,
        including year determination for updates.

        Args:
            calendar_name: Name of the calendar
            source_calendar: Source calendar data from ingestion
            is_new: True if creating new calendar, False if updating existing
            template: Optional template configuration
            year: Year to replace (required for updates if multi-year source)

        Returns:
            ProcessingResult with processed calendar, summary, and year

        Raises:
            CalendarNotFoundError: If calendar not found during update
            InvalidYearError: If year validation fails
            AmbiguousYearError: If year cannot be determined from multi-year source
        """
        if is_new:
            # Creating new calendar
            result, processing_summary = self.create_calendar_from_source(
                source_calendar, calendar_name, template
            )
            return ProcessingResult(
                result=result,
                processing_summary=processing_summary,
                year=None,
            )
        else:
            # Updating existing calendar - determine year if not specified
            effective_year = self._determine_year(source_calendar, year)

            result, processing_summary = self.compose_calendar_with_source(
                calendar_name, source_calendar, effective_year, self.repository, template
            )
            return ProcessingResult(
                result=result,
                processing_summary=processing_summary,
                year=effective_year,
            )

    def _determine_year(self, source_calendar: Calendar, year: int | None) -> int:
        """
        Determine the year to use for calendar update.

        Args:
            source_calendar: Source calendar to check
            year: Explicit year override (if provided)

        Returns:
            Year to use for update

        Raises:
            InvalidYearError: If year cannot be determined from multi-year source
        """
        if year is not None:
            return year

        if source_calendar.year is not None:
            return source_calendar.year

        # Infer year from events
        years = {event.date.year for event in source_calendar.events}
        if len(years) != 1:
            raise InvalidYearError(
                f"Source calendar contains events from multiple years: {years}. "
                "Please specify --year option when updating an existing calendar."
            )

        return years.pop()
