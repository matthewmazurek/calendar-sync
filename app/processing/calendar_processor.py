"""High-level processor for event lists."""

import logging

from app.models.event import Event
from app.models.template import CalendarTemplate
from app.processing.event_processor import process_events_with_template

logger = logging.getLogger(__name__)


class EventListProcessor:
    """Processor that operates on lists of events."""

    def process(
        self, events: list[Event], template: CalendarTemplate | None = None
    ) -> tuple[list[Event], dict]:
        """Process events and return processed events with summary.

        Args:
            events: List of events to process
            template: Optional template configuration

        Returns:
            Tuple of (processed_events, summary_dict) where summary_dict contains
            event counts by type before and after processing.
        """
        logger.info(f"Processing {len(events)} events")
        if template:
            logger.info(
                f"Processing with template: {template.name} (version {template.version})"
            )
        else:
            logger.warning(
                "No template provided - using minimal fallback template for processing."
            )
        processed_events, summary = process_events_with_template(events, template)
        logger.info(f"Processed to {len(processed_events)} events")
        return processed_events, summary
