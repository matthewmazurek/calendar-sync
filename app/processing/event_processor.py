"""Event processor using pipeline with Pydantic Event models."""

from typing import List, Tuple

from app.models.event import Event
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
