"""High-level processor for Calendar objects."""

import logging

from app.models.calendar import Calendar
from app.models.template import CalendarTemplate
from app.processing.event_processor import process_events_with_template

logger = logging.getLogger(__name__)


class CalendarProcessor:
    """High-level processor that operates on Calendar objects."""

    def process(
        self, calendar: Calendar, template: CalendarTemplate | None = None
    ) -> tuple[Calendar, dict]:
        """Process calendar events and return processed calendar with summary.

        Args:
            calendar: Calendar to process
            template: Optional template configuration

        Returns:
            Tuple of (processed_calendar, summary_dict) where summary_dict contains
            event counts by type before and after processing.
        """
        logger.info(f"Processing {len(calendar.events)} events")
        if template:
            logger.info(
                f"Processing with template: {template.name} (version {template.version})"
            )
        else:
            logger.warning(
                "No template provided - using minimal fallback template for processing."
            )
        processed_events, summary = process_events_with_template(
            calendar.events, template
        )
        logger.info(f"Processed to {len(processed_events)} events")
        return (
            Calendar(
                events=processed_events,
                revised_date=calendar.revised_date,
                year=calendar.year,
            ),
            summary,
        )
