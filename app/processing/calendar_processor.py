"""High-level processor for Calendar objects."""

import logging
from typing import Tuple

from app.models.calendar import Calendar
from app.processing.event_processor import process_events

logger = logging.getLogger(__name__)


class CalendarProcessor:
    """High-level processor that operates on Calendar objects."""

    def process(self, calendar: Calendar) -> Tuple[Calendar, dict]:
        """Process calendar events and return processed calendar with summary.
        
        Returns:
            Tuple of (processed_calendar, summary_dict) where summary_dict contains
            event counts by type before and after processing.
        """
        logger.info(f"Processing {len(calendar.events)} events")
        processed_events, summary = process_events(calendar.events)
        logger.info(f"Processed to {len(processed_events)} events")
        return Calendar(
            events=processed_events,
            revised_date=calendar.revised_date,
            year=calendar.year,
        ), summary
