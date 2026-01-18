"""Calendar manager with merge strategy support."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from app.exceptions import CalendarNotFoundError, InvalidYearError
from app.models.calendar import Calendar
from app.models.event import Event
from app.models.ingestion import RawIngestion
from app.models.template import CalendarTemplate
from app.processing.calendar_processor import EventListProcessor
from app.processing.merge_strategies import (
    Add,
    MergeStrategy,
    ReplaceByYear,
    UpsertById,
    infer_year,
    merge_events,
)

logger = logging.getLogger(__name__)


class CalendarRepository(Protocol):
    """Protocol for calendar repository."""

    def load_calendar(self, name: str) -> Calendar | None:
        """Load calendar by name."""
        ...

    def save(self, calendar: Calendar) -> Path:
        """Save calendar."""
        ...


@dataclass
class ProcessingResult:
    """Result from calendar processing operations."""

    calendar: Calendar
    processing_summary: dict
    year: int | None  # Year being updated (None for new calendars or Add strategy)


class CalendarManager:
    """High-level calendar management operations with merge strategies."""

    def __init__(self, repository: CalendarRepository):
        """Initialize with repository (dependency injection)."""
        self.repository = repository
        self.processor = EventListProcessor()

    def create_calendar(
        self,
        calendar_name: str,
        raw: RawIngestion,
        template: CalendarTemplate | None = None,
    ) -> ProcessingResult:
        """Create a new calendar from raw ingestion data.

        Args:
            calendar_name: Name for the new calendar
            raw: Raw ingestion data (events + revised_at)
            template: Optional template configuration

        Returns:
            ProcessingResult with the new calendar
        """
        # Process events
        processed_events, processing_summary = self.processor.process(
            raw.events, template
        )

        # Create calendar with metadata
        now = datetime.now()
        calendar = Calendar(
            events=processed_events,
            name=calendar_name,
            created=now,
            last_updated=now,
            source_revised_at=raw.revised_at,
            template_name=template.name if template else None,
            template_version=template.version if template else None,
        )

        return ProcessingResult(
            calendar=calendar,
            processing_summary=processing_summary,
            year=None,
        )

    def update_calendar(
        self,
        calendar_name: str,
        raw: RawIngestion,
        strategy: MergeStrategy,
        template: CalendarTemplate | None = None,
    ) -> ProcessingResult:
        """Update an existing calendar using a merge strategy.

        Args:
            calendar_name: Name of the calendar to update
            raw: Raw ingestion data (events + revised_at)
            strategy: Merge strategy to use
            template: Optional template configuration

        Returns:
            ProcessingResult with the updated calendar

        Raises:
            CalendarNotFoundError: If calendar doesn't exist
        """
        # Load existing calendar
        existing = self.repository.load_calendar(calendar_name)
        if existing is None:
            raise CalendarNotFoundError(f"Calendar '{calendar_name}' not found")

        # Process new events
        processed_events, processing_summary = self.processor.process(
            raw.events, template
        )

        # Merge events using strategy
        merged_events = merge_events(existing.events, processed_events, strategy)

        # Determine year for result (useful for reporting)
        result_year = self._get_strategy_year(strategy)

        # Update calendar
        updated_calendar = Calendar(
            events=merged_events,
            name=existing.name,
            created=existing.created,
            last_updated=datetime.now(),
            source=existing.source,
            source_revised_at=raw.revised_at if raw.revised_at else existing.source_revised_at,
            composed_from=existing.composed_from,
            template_name=template.name if template else existing.template_name,
            template_version=template.version if template else existing.template_version,
        )

        return ProcessingResult(
            calendar=updated_calendar,
            processing_summary=processing_summary,
            year=result_year,
        )

    def create_or_update(
        self,
        calendar_name: str,
        raw: RawIngestion,
        is_new: bool,
        template: CalendarTemplate | None = None,
        strategy: MergeStrategy | None = None,
        year: int | None = None,
    ) -> ProcessingResult:
        """Create new calendar or update existing one.

        This is a convenience method that handles both create and update cases.

        Args:
            calendar_name: Name of the calendar
            raw: Raw ingestion data from ingestion
            is_new: True if creating new calendar, False if updating existing
            template: Optional template configuration
            strategy: Merge strategy (auto-determined if None)
            year: Year for ReplaceByYear (used if strategy not specified)

        Returns:
            ProcessingResult with processed calendar, summary, and year

        Raises:
            CalendarNotFoundError: If calendar not found during update
            InvalidYearError: If year cannot be determined for ReplaceByYear
        """
        if is_new:
            return self.create_calendar(calendar_name, raw, template)

        # Determine strategy if not provided
        if strategy is None:
            # Default: ReplaceByYear using inferred or provided year
            effective_year = self._determine_year(raw.events, year)
            strategy = ReplaceByYear(effective_year)

        return self.update_calendar(calendar_name, raw, strategy, template)

    def _determine_year(self, events: list[Event], year: int | None) -> int:
        """Determine the year to use for ReplaceByYear strategy.

        Args:
            events: Events to check
            year: Explicit year override (if provided)

        Returns:
            Year to use

        Raises:
            InvalidYearError: If year cannot be determined from multi-year events
        """
        if year is not None:
            return year

        inferred = infer_year(events)
        if inferred is None:
            raise InvalidYearError(
                "Source contains events from multiple years. "
                "Please specify --year option when updating an existing calendar."
            )

        return inferred

    def _get_strategy_year(self, strategy: MergeStrategy) -> int | None:
        """Extract year from strategy if applicable."""
        match strategy:
            case ReplaceByYear(year=y):
                return y
            case _:
                return None


def get_default_strategy_for_source(
    source_extension: str,
    events: list[Event],
    year_override: int | None = None,
) -> MergeStrategy:
    """Get the default merge strategy based on source file type.

    Args:
        source_extension: File extension (e.g., '.docx', '.ics', '.json')
        events: Events from the source (used to infer year for Word)
        year_override: Explicit year override

    Returns:
        Default merge strategy for the source type

    Raises:
        InvalidYearError: If Word source has multi-year events and no override
    """
    ext = source_extension.lower().lstrip(".")

    if ext in ("doc", "docx"):
        # Word documents: ReplaceByYear (they're year-specific schedules)
        year = year_override or infer_year(events)
        if year is None:
            raise InvalidYearError(
                "Word document contains events from multiple years. "
                "Please specify --year option."
            )
        return ReplaceByYear(year)

    elif ext == "ics":
        # ICS files: UpsertById (they have UIDs for matching)
        return UpsertById()

    else:
        # JSON and other formats: Add by default
        return Add()
