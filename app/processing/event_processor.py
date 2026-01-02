"""Event processor using pipeline with Pydantic Event models."""

from typing import List, Optional, Tuple

from app.models.event import Event
from app.models.template import CalendarTemplate
from app.processing.configurable_processor import ConfigurableEventProcessor
from app.processing.event_type_processors import (
    AllDayEventProcessor,
    EventProcessingPipeline,
    OnCallEventProcessor,
    RegularEventProcessor,
)


def process_events(events: List[Event]) -> Tuple[List[Event], dict]:
    """
    Process a list of events through all necessary transformations.
    This is the main entry point for event processing.

    Args:
        events: List of Event models to process

    Returns:
        Tuple of (processed_events, summary_dict) where summary_dict contains
        event counts by type before and after processing.
    """
    # Create pipeline with type-specific processors
    processors = [
        OnCallEventProcessor(),
        AllDayEventProcessor(),
        RegularEventProcessor(),
    ]
    pipeline = EventProcessingPipeline(processors)

    # Process events through pipeline
    return pipeline.process(events)


def process_events_with_template(
    events: List[Event], template: Optional[CalendarTemplate]
) -> Tuple[List[Event], dict]:
    """
    Process events using template configuration.

    Args:
        events: List of Event models to process
        template: Optional template configuration

    Returns:
        Tuple of (processed_events, summary_dict)
    """
    if template is None:
        # Fall back to legacy processing
        return process_events(events)

    # Count events by type before processing
    from collections import defaultdict

    input_type_counts = defaultdict(int)
    for event in events:
        type_value = event.type or event.get_type_enum().value
        input_type_counts[type_value] += 1

    # Process with template
    processor = ConfigurableEventProcessor(template)
    processed_events = processor.process(events)

    # Count events by type after processing
    output_type_counts = defaultdict(int)
    for event in processed_events:
        type_value = event.type or event.get_type_enum().value
        output_type_counts[type_value] += 1

    summary = {
        "input_counts": dict(input_type_counts),
        "output_counts": dict(output_type_counts),
        "input_total": len(events),
        "output_total": len(processed_events),
    }

    return processed_events, summary
