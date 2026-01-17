"""Processing layer for calendar events."""

from app.processing.calendar_manager import CalendarManager, ProcessingResult
from app.processing.calendar_merger import replace_year_in_calendar
from app.processing.calendar_processor import CalendarProcessor
from app.processing.configurable_processor import ConfigurableEventProcessor
from app.processing.event_processor import process_events_with_template

__all__ = [
    "CalendarManager",
    "CalendarProcessor",
    "ConfigurableEventProcessor",
    "ProcessingResult",
    "process_events_with_template",
    "replace_year_in_calendar",
]
