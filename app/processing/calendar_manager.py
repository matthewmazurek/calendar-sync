"""Calendar manager with simplified create/compose operations."""

from datetime import datetime
from typing import Protocol

from app.exceptions import CalendarNotFoundError, InvalidYearError
from app.models.calendar import Calendar
from app.models.metadata import CalendarMetadata, CalendarWithMetadata
from app.models.template import CalendarTemplate
from app.processing.calendar_merger import replace_year_in_calendar
from app.processing.calendar_processor import CalendarProcessor


class CalendarRepository(Protocol):
    """Protocol for calendar repository."""

    def load_calendar(
        self, name: str, format: str = "ics"
    ) -> CalendarWithMetadata | None:
        """Load calendar by name."""
        ...

    def save_calendar(
        self, calendar: Calendar, metadata: CalendarMetadata, writer
    ) -> str:
        """Save calendar with metadata."""
        ...


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
            format="ics",  # Default format
            source_revised_at=source_data.revised_date,  # Extract from Calendar
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
            format=existing_metadata.format,
            source_revised_at=(
                source_data.revised_date
                if source_data.revised_date
                else existing_metadata.source_revised_at
            ),
        )

        return (
            CalendarWithMetadata(calendar=merged_calendar, metadata=updated_metadata),
            processing_summary,
        )
