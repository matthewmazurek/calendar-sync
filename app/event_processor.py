from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

# Constants
WORK_LOCATION = "Foothills Medical Centre, 1403 29 St NW, Calgary AB T2N 2T9, Canada"


def is_oncall_event(event: Dict) -> bool:
    """Check if an event is an on-call event."""
    return "on call" in event["title"].lower()


def get_oncall_type(event: Dict) -> Optional[str]:
    """Extract the base on-call type, ignoring overnight time ranges."""
    if not is_oncall_event(event):
        return None

    # Split on "on call" and take the first part
    parts = event["title"].lower().split("on call")
    if not parts:
        return None

    # Clean up the type (remove extra spaces, etc.)
    oncall_type = parts[0].strip()
    return oncall_type if oncall_type else "primary"


def are_consecutive_dates(date1: str, date2: str) -> bool:
    """Check if two dates are consecutive."""
    d1 = datetime.strptime(date1, "%Y-%m-%d")
    d2 = datetime.strptime(date2, "%Y-%m-%d")
    return (d2 - d1).days == 1


def is_overnight_event(event: Dict) -> bool:
    """Check if an event is an overnight event (end time is earlier than start time, or same time)."""
    if "start" not in event or "end" not in event:
        return False
    start_time = int(event["start"])
    end_time = int(event["end"])
    return start_time >= end_time


def format_time(time_str: str) -> str:
    """Convert 24-hour time format to 12-hour format with AM/PM."""
    time_int = int(time_str)
    hour = time_int // 100
    minute = time_int % 100
    period = "AM" if hour < 12 else "PM"
    if hour == 0:
        hour = 12
    elif hour > 12:
        hour -= 12
    return f"{hour}:{minute:02d} {period}"


def process_overnight_event(event: Dict) -> Dict:
    """Convert an overnight event to an all-day event while preserving its on-call type."""
    if not is_overnight_event(event):
        return event

    # Get the base on-call type
    oncall_type = get_oncall_type(event)
    if not oncall_type:
        return event

    # Format the time range
    time_range = f"{format_time(event['start'])} to {format_time(event['end'])}"

    # Create new title preserving the on-call type
    new_title = f"{oncall_type.title()} on call {time_range}"

    # Create new event
    new_event = event.copy()
    new_event["title"] = new_title
    new_event.pop("start", None)
    new_event.pop("end", None)
    return new_event


def is_all_day_event(event: Dict) -> bool:
    """Check if an event is an all-day event (no start/end times)."""
    return "start" not in event and "end" not in event


def consolidate_oncall_events(events: List[Dict]) -> List[Dict]:
    """
    Consolidate consecutive on-call events (of any duration) and all-day events into multi-day events.
    For each contiguous on-call stretch, output a multi-day event. For each overnight on-call day within the stretch, output a separate all-day event. If the stretch is only one day and it's overnight, only output the overnight event.
    All-day non-on-call events are grouped by title.
    """
    # First, identify overnight events and get their on-call type
    overnight_events = []
    regular_events = []
    for event in events:
        if is_oncall_event(event) and is_overnight_event(event):
            oncall_type = get_oncall_type(event)
            processed_event = process_overnight_event(event)
            processed_event["_oncall_type"] = oncall_type
            processed_event["_time_range"] = processed_event["title"].split("on call ")[
                1
            ]
            overnight_events.append(processed_event)
        else:
            regular_events.append(event)

    # Group on-call events by type (regardless of start/end)
    oncall_by_type = defaultdict(list)
    all_day_by_title = defaultdict(list)
    other_events = []
    for event in regular_events:
        if is_oncall_event(event):
            oncall_by_type[get_oncall_type(event)].append(event)
        elif is_all_day_event(event):
            all_day_by_title[event["title"]].append(event)
        else:
            other_events.append(event)

    # Add overnight events to their respective on-call groups
    for event in overnight_events:
        if "_oncall_type" in event:
            oncall_by_type[event["_oncall_type"]].append(event)

    consolidated = []
    # Consolidate on-call events by type
    for oncall_type, events_of_type in oncall_by_type.items():
        # Sort by date
        events_of_type.sort(key=lambda e: e["date"])
        # Map date to event
        events_by_date = {ev["date"]: ev for ev in events_of_type}
        all_dates = sorted(events_by_date.keys())
        start_idx = 0
        while start_idx < len(all_dates):
            end_idx = start_idx
            while end_idx + 1 < len(all_dates) and are_consecutive_dates(
                all_dates[end_idx], all_dates[end_idx + 1]
            ):
                end_idx += 1
            # This is a contiguous stretch
            stretch_dates = all_dates[start_idx : end_idx + 1]
            stretch_events = [events_by_date[d] for d in stretch_dates]
            # Identify overnight events in this stretch
            overnight_in_stretch = [e for e in stretch_events if "_time_range" in e]
            # If the stretch is only one day and it's overnight, only output the overnight event
            if len(stretch_dates) == 1 and overnight_in_stretch:
                overnight_event = overnight_in_stretch[0].copy()
                overnight_event.pop("_oncall_type", None)
                overnight_event.pop("_time_range", None)
                consolidated.append(overnight_event)
            else:
                # Output the multi-day event for the stretch
                first_event = events_by_date[stretch_dates[0]].copy()
                first_event["end_date"] = stretch_dates[-1]
                first_event.pop("start", None)
                first_event.pop("end", None)
                first_event.pop("_oncall_type", None)
                first_event.pop("_time_range", None)
                consolidated.append(first_event)
                # Output each overnight event as a separate all-day event
                for overnight_event in overnight_in_stretch:
                    oe = overnight_event.copy()
                    oe.pop("_oncall_type", None)
                    oe.pop("_time_range", None)
                    consolidated.append(oe)
            start_idx = end_idx + 1

    # Consolidate all-day non-on-call events by title
    for title, events_of_title in all_day_by_title.items():
        events_by_date = {ev["date"]: ev for ev in events_of_title}
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
                consolidated_event = first_event.copy()
                consolidated_event["end_date"] = last_date
                consolidated.append(consolidated_event)
            start_idx = end_idx + 1

    # Combine all events and sort by date
    all_events = consolidated + other_events
    all_events.sort(key=lambda e: e["date"])
    return all_events


def create_consolidated_event(events: List[Dict]) -> Dict:
    """Create a consolidated event from a sequence of on-call events."""
    if not events:
        raise ValueError("Cannot create consolidated event from empty sequence")

    first_event = events[0]
    last_event = events[-1]

    # Create the consolidated event
    consolidated = first_event.copy()
    consolidated["end_date"] = last_event["date"]

    # If multi-day, remove start/end times
    if consolidated["date"] != consolidated["end_date"]:
        consolidated.pop("start", None)
        consolidated.pop("end", None)

    return consolidated


def include_work_location(event_title: str) -> str | None:
    """
    Check if an event should have work location information based on its title.

    Args:
        event_title: The title of the event

    Returns:
        WORK_LOCATION if the event should have location (contains 'endo', 'ccsc', 'clinic', or 'on call'),
        None otherwise
    """
    keywords = ["endo", "ccsc", "clinic", "on call"]
    title_lower = event_title.lower()
    return (
        WORK_LOCATION if any(keyword in title_lower for keyword in keywords) else None
    )


def process_events(events: List[Dict]) -> List[Dict]:
    """
    Process a list of events through all necessary transformations.
    This is the main entry point for event processing.

    Args:
        events: List of event dictionaries to process

    Returns:
        List of processed event dictionaries
    """
    # First consolidate events
    processed_events = consolidate_oncall_events(events)

    # Add work location to events that should have it
    for event in processed_events:
        location = include_work_location(event["title"])
        if location:
            event["location"] = location

    return processed_events
