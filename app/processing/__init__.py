"""Processing layer for calendar events."""

from app.processing.calendar_manager import CalendarManager, ProcessingResult
from app.processing.calendar_processor import EventListProcessor
from app.processing.configurable_processor import ConfigurableEventProcessor
from app.processing.event_processor import process_events_with_template
from app.processing.merge_strategies import (
    Add,
    MergeStrategy,
    ReplaceByRange,
    ReplaceByYear,
    UpsertById,
    infer_year,
    merge_events,
)

__all__ = [
    "CalendarManager",
    "EventListProcessor",
    "ConfigurableEventProcessor",
    "ProcessingResult",
    "process_events_with_template",
    "Add",
    "MergeStrategy",
    "ReplaceByRange",
    "ReplaceByYear",
    "UpsertById",
    "infer_year",
    "merge_events",
]
