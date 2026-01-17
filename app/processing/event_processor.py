"""Event processor using template-driven configuration."""

import logging
from collections import defaultdict

from app.models.event import Event
from app.models.template import CalendarTemplate
from app.processing.configurable_processor import ConfigurableEventProcessor

logger = logging.getLogger(__name__)


def process_events_with_template(
    events: list[Event], template: CalendarTemplate | None
) -> tuple[list[Event], dict]:
    """
    Process events using template configuration.

    Args:
        events: List of Event models to process
        template: Optional template configuration

    Returns:
        Tuple of (processed_events, summary_dict)
    """
    if template is None:
        from app.models.template_loader import build_default_template

        logger.warning(
            "No template provided - using minimal fallback template for processing."
        )
        template = build_default_template()

    # Count events by type before processing (normalize to lowercase)
    input_type_counts: dict[str, int] = defaultdict(int)
    for event in events:
        type_value = event.type or event.get_type_enum().value.lower()
        input_type_counts[type_value] += 1

    # Process with template
    processor = ConfigurableEventProcessor(template)
    processed_events = processor.process(events)

    # Count events by type after processing (normalize to lowercase)
    output_type_counts: dict[str, int] = defaultdict(int)
    for event in processed_events:
        type_value = event.type or event.get_type_enum().value.lower()
        output_type_counts[type_value] += 1

    summary = {
        "input_counts": dict(input_type_counts),
        "output_counts": dict(output_type_counts),
        "input_total": len(events),
        "output_total": len(processed_events),
    }

    return processed_events, summary
