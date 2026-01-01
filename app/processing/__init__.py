"""Processing layer for calendar events."""

from app.processing.calendar_merger import replace_year_in_calendar
from app.processing.calendar_processor import CalendarProcessor
from app.processing.event_processor import process_events
from app.processing.event_type_processors import (
    AllDayEventProcessor,
    EventProcessingPipeline,
    EventProcessor,
    OnCallEventProcessor,
    RegularEventProcessor,
)

__all__ = [
    "EventProcessor",
    "EventProcessingPipeline",
    "OnCallEventProcessor",
    "AllDayEventProcessor",
    "RegularEventProcessor",
    "process_events",
    "CalendarProcessor",
    "replace_year_in_calendar",
]
