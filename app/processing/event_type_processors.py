"""Type-specific event processors."""

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import List, Protocol, Tuple

from app.models.event import Event, EventType

logger = logging.getLogger(__name__)

WORK_LOCATION = "Foothills Medical Centre, 1403 29 St NW, Calgary AB T2N 2T9, Canada"


class EventProcessor(Protocol):
    """Protocol for event processors."""

    def can_process(self, event: Event) -> bool:
        """Check if this processor can handle the event."""
        ...

    def process(self, events: List[Event]) -> List[Event]:
        """Process a list of events."""
        ...


def are_consecutive_dates(date1: date, date2: date) -> bool:
    """Check if two dates are consecutive."""
    return (date2 - date1).days == 1


def is_weekend_stretch(stretch_dates: List[date]) -> bool:
    """Check if a stretch of dates is a weekend stretch (Friday-Sunday)."""
    if not stretch_dates:
        return False

    first_date = stretch_dates[0]
    first_weekday = first_date.weekday()  # Monday=0, Friday=4, Sunday=6

    if first_weekday != 4:  # Not Friday
        return False

    # Check if it includes Saturday (weekday == 5) or Sunday (weekday == 6)
    for d in stretch_dates:
        if d.weekday() in [5, 6]:
            return True

    return False


def format_time(time_obj) -> str:
    """Convert time object to 12-hour format with AM/PM."""
    hour = time_obj.hour
    minute = time_obj.minute
    period = "AM" if hour < 12 else "PM"
    if hour == 0:
        hour = 12
    elif hour > 12:
        hour -= 12
    return f"{hour}:{minute:02d} {period}"


def get_oncall_type(event: Event) -> str | None:
    """Extract the base on-call type from event title."""
    if event.type != EventType.ON_CALL:
        return None

    title_lower = event.title.lower()
    parts = title_lower.split("on call")
    if not parts:
        return None

    oncall_type = parts[0].strip()
    return oncall_type if oncall_type else "primary"


class OnCallEventProcessor:
    """Processor for On Call events."""

    def can_process(self, event: Event) -> bool:
        """Check if event is an on-call event."""
        return event.type == EventType.ON_CALL

    def process(self, events: List[Event]) -> List[Event]:
        """Consolidate on-call events by date."""
        if not events:
            return []

        logger.info(f"Processing {len(events)} on-call events")

        # Separate overnight events from regular events
        # Store overnight events as tuples (event, oncall_type, time_range)
        overnight_events: List[Tuple[Event, str, str]] = []
        regular_events = []

        for event in events:
            if self._is_overnight_oncall(event):
                processed, oncall_type, time_range = self._process_overnight_oncall(event)
                overnight_events.append((processed, oncall_type, time_range))
            else:
                regular_events.append(event)

        # Group by on-call type, using consistent structure: (event, time_range or None)
        oncall_by_type = defaultdict(list)
        for event in regular_events:
            oncall_type = get_oncall_type(event)
            oncall_by_type[oncall_type].append((event, None))

        # Add overnight events to their respective groups
        for event, oncall_type, time_range in overnight_events:
            oncall_by_type[oncall_type].append((event, time_range))

        consolidated = []
        for oncall_type, events_of_type in oncall_by_type.items():
            # Sort by date
            events_of_type.sort(key=lambda x: x[0].date)
            events_by_date = {event.date: (event, time_range) for event, time_range in events_of_type}
            all_dates = sorted(events_by_date.keys())

            start_idx = 0
            while start_idx < len(all_dates):
                end_idx = start_idx
                while end_idx + 1 < len(all_dates) and are_consecutive_dates(
                    all_dates[end_idx], all_dates[end_idx + 1]
                ):
                    end_idx += 1

                stretch_dates = all_dates[start_idx : end_idx + 1]
                stretch_events = [events_by_date[d] for d in stretch_dates]
                overnight_in_stretch = [
                    (event, time_range) for event, time_range in stretch_events if time_range is not None
                ]

                if len(stretch_dates) == 1 and overnight_in_stretch:
                    # Single day overnight - output only the overnight event
                    overnight_event, _ = overnight_in_stretch[0]
                    consolidated.append(overnight_event)
                else:
                    # Multi-day stretch - output consolidated event
                    first_event, _ = events_by_date[stretch_dates[0]]
                    # Extract base title (remove time range if present)
                    base_title = first_event.title
                    if " on call " in base_title and " to " in base_title:
                        # Extract base on-call type
                        base_title = base_title.split(" on call ")[0] + " on call"

                    consolidated_event = Event(
                        title=base_title,
                        date=stretch_dates[0],
                        end_date=stretch_dates[-1],
                        location=first_event.location,
                    )
                    consolidated.append(consolidated_event)

                    # Output individual overnight events (skip for weekend stretches)
                    if not is_weekend_stretch(stretch_dates):
                        for overnight_event, _ in overnight_in_stretch:
                            consolidated.append(overnight_event)

                start_idx = end_idx + 1

        return consolidated

    def _is_overnight_oncall(self, event: Event) -> bool:
        """Check if on-call event is overnight."""
        if not event.start or not event.end:
            return False
        # Overnight if start >= end (e.g., 2300-0700)
        return event.start >= event.end

    def _process_overnight_oncall(self, event: Event) -> Tuple[Event, str, str]:
        """Convert overnight on-call event to all-day with time range in title."""
        oncall_type = get_oncall_type(event)
        if not oncall_type:
            return (event, "", "")

        time_range = f"{format_time(event.start)} to {format_time(event.end)}"
        new_title = f"{oncall_type.title()} on call {time_range}"

        processed = Event(
            title=new_title,
            date=event.date,
            location=event.location,
        )
        return (processed, oncall_type, time_range)


class AllDayEventProcessor:
    """Processor for all-day events."""

    def can_process(self, event: Event) -> bool:
        """Check if event is all-day."""
        return event.is_all_day

    def process(self, events: List[Event]) -> List[Event]:
        """Consolidate all-day events by title."""
        if not events:
            return []

        logger.info(f"Processing {len(events)} all-day events")

        # Group by title
        by_title = defaultdict(list)
        for event in events:
            by_title[event.title].append(event)

        consolidated = []
        for title, events_of_title in by_title.items():
            events_by_date = {e.date: e for e in events_of_title}
            all_dates = sorted(events_by_date.keys())

            start_idx = 0
            while start_idx < len(all_dates):
                end_idx = start_idx
                while end_idx + 1 < len(all_dates) and are_consecutive_dates(
                    all_dates[end_idx], all_dates[end_idx + 1]
                ):
                    end_idx += 1

                first_date = all_dates[start_idx]
                last_date = all_dates[end_idx]
                first_event = events_by_date[first_date]

                if start_idx == end_idx:
                    consolidated.append(first_event)
                else:
                    consolidated_event = Event(
                        title=first_event.title,
                        date=first_date,
                        end_date=last_date,
                        location=first_event.location,
                    )
                    consolidated.append(consolidated_event)

                start_idx = end_idx + 1

        logger.info(f"Consolidated {len(events)} all-day events to {len(consolidated)} events")
        return consolidated


class RegularEventProcessor:
    """Processor for regular timed events."""

    def can_process(self, event: Event) -> bool:
        """Check if event is a regular timed event."""
        return not event.is_all_day and event.type != EventType.ON_CALL

    def process(self, events: List[Event]) -> List[Event]:
        """Process regular events (overnight splitting, location assignment)."""
        logger.info(f"Processing {len(events)} regular events")
        processed = []
        for event in events:
            # Handle overnight events (spanning midnight)
            if event.is_overnight:
                processed.extend(self._split_overnight_event(event))
            else:
                # Add location if required
                if event.requires_location and not event.location:
                    event = event.model_copy(update={"location": WORK_LOCATION})
                processed.append(event)
        logger.info(f"Processed {len(events)} regular events to {len(processed)} events")
        return processed

    def _split_overnight_event(self, event: Event) -> List[Event]:
        """Split overnight event into two events."""
        if not event.is_overnight or not event.start or not event.end:
            return [event]

        # Create first day event
        first_event = Event(
            title=event.title,
            date=event.date,
            start=event.start,
            end=None,  # End at midnight
            location=event.location,
        )

        # Create second day event
        second_event = Event(
            title=event.title,
            date=event.end_date,
            start=None,  # Start at midnight
            end=event.end,
            location=event.location,
        )

        return [first_event, second_event]


class EventProcessingPipeline:
    """Pipeline for processing events by type."""

    def __init__(self, processors: List[EventProcessor]):
        """Initialize pipeline with processors."""
        self.processors = processors

    def process(self, events: List[Event]) -> Tuple[List[Event], dict]:
        """Route events to appropriate processors based on type.
        
        Returns:
            Tuple of (processed_events, summary_dict) where summary_dict contains
            event counts by type before and after processing.
        """
        if not events:
            return [], {}

        logger.info(f"Processing pipeline: {len(events)} events")

        # Count events by type before processing
        from app.models.event import EventType
        input_type_counts = defaultdict(int)
        for event in events:
            input_type_counts[event.type] += 1

        # Group events by type
        by_type = defaultdict(list)
        for event in events:
            # Find processor that can handle this event
            processed = False
            for processor in self.processors:
                if processor.can_process(event):
                    by_type[processor].append(event)
                    processed = True
                    break
            if not processed:
                # No processor found, keep as-is
                by_type[None].append(event)

        # Process each group and track output counts
        processed_events = []
        output_type_counts = defaultdict(int)
        for processor, event_group in by_type.items():
            if processor is None:
                processed_events.extend(event_group)
                for event in event_group:
                    output_type_counts[event.type] += 1
            else:
                processed = processor.process(event_group)
                processed_events.extend(processed)
                for event in processed:
                    output_type_counts[event.type] += 1

        # Sort by date
        processed_events.sort(key=lambda e: e.date)

        # Add location to events that need it
        final_events = []
        for event in processed_events:
            if not event.location:
                title_lower = event.title.lower()
                keywords = ["endo", "ccsc", "clinic", "on call"]
                if any(keyword in title_lower for keyword in keywords):
                    event = event.model_copy(update={"location": WORK_LOCATION})
            final_events.append(event)
        
        # Build summary
        summary = {
            "input_counts": dict(input_type_counts),
            "output_counts": dict(output_type_counts),
            "input_total": len(events),
            "output_total": len(final_events),
        }
        
        logger.info(f"Pipeline complete: {len(events)} input events -> {len(final_events)} final events")
        return final_events, summary
