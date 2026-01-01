import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List

from icalendar import Calendar

from app.event_processor import WORK_LOCATION


def load_existing_events(ics_path: Path) -> List[Dict]:
    """
    Parse existing ICS file to extract events.

    Args:
        ics_path: Path to the existing ICS file

    Returns:
        List of event dictionaries in the format expected by generate_ical
    """
    if not ics_path.exists():
        return []

    try:
        with open(ics_path, "r") as f:
            cal = Calendar.from_ical(f.read())
    except Exception:
        # If we can't parse the file, return empty list
        return []

    events = []

    for component in cal.walk():
        if component.name == "VEVENT":
            event_dict = _ics_event_to_dict(component)
            if event_dict:
                events.append(event_dict)

    return events


def _ics_event_to_dict(vevent) -> Dict | None:
    """
    Convert an ICS VEVENT component back to our event dictionary format.

    Args:
        vevent: icalendar Event component

    Returns:
        Event dictionary with keys: date, title, start, end, end_date, location
    """
    # Extract title
    title = str(vevent.get("summary", ""))
    if not title:
        return None

    # Extract location
    location = str(vevent.get("location", "")) if vevent.get("location") else None
    if location == "":
        location = None
    elif (
        location
        and "Foothills Medical Centre" in location
        and "1403 29 St NW" in location
    ):
        # Convert back to the work location constant
        location = WORK_LOCATION

    # Extract start and end times
    dtstart = vevent.get("dtstart")
    dtend = vevent.get("dtend")

    if not dtstart:
        return None

    # Convert dtstart to datetime object
    if hasattr(dtstart.dt, "date") and hasattr(dtstart.dt, "time"):
        # It's a datetime (timed event)
        start_dt = dtstart.dt
        start_date = start_dt.date()
        start_time = start_dt.time()

        # Check if it's a multi-day event
        if dtend:
            if hasattr(dtend.dt, "date") and hasattr(dtend.dt, "time"):
                # dtend is also a datetime
                end_dt = dtend.dt
                end_date = end_dt.date()
                end_time = end_dt.time()

                if start_date != end_date:
                    # Multi-day timed event
                    return {
                        "title": title,
                        "date": start_date.strftime("%Y-%m-%d"),
                        "start": start_time.strftime("%H%M"),
                        "end": end_time.strftime("%H%M"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "location": location,
                    }
                else:
                    # Single-day timed event
                    return {
                        "title": title,
                        "date": start_date.strftime("%Y-%m-%d"),
                        "start": start_time.strftime("%H%M"),
                        "end": end_time.strftime("%H%M"),
                        "location": location,
                    }
            else:
                # dtend is a date (shouldn't happen with timed events, but handle it)
                end_date = dtend.dt
                return {
                    "title": title,
                    "date": start_date.strftime("%Y-%m-%d"),
                    "start": start_time.strftime("%H%M"),
                    "end": start_time.strftime("%H%M"),
                    "location": location,
                }
        else:
            # No dtend, single-day timed event
            return {
                "title": title,
                "date": start_date.strftime("%Y-%m-%d"),
                "start": start_time.strftime("%H%M"),
                "end": start_time.strftime("%H%M"),  # Same as start if no end
                "location": location,
            }
    else:
        # It's a date (all-day event)
        start_date = dtstart.dt

        if dtend:
            end_date = dtend.dt
            # For all-day events, dtend is exclusive, so subtract 1 day
            if isinstance(end_date, date):
                actual_end_date = end_date
            else:
                actual_end_date = end_date.date()

            # Check if it's multi-day (accounting for the +1 day in dtend)
            # If dtend is start_date + 1, it's a single-day event
            from datetime import timedelta

            if actual_end_date == start_date + timedelta(days=1):
                # Single-day all-day event
                return {
                    "title": title,
                    "date": start_date.strftime("%Y-%m-%d"),
                    "location": location,
                }
            else:
                # Multi-day all-day event
                return {
                    "title": title,
                    "date": start_date.strftime("%Y-%m-%d"),
                    "end_date": (actual_end_date - timedelta(days=1)).strftime(
                        "%Y-%m-%d"
                    ),
                    "location": location,
                }
        else:
            # Single-day all-day event
            return {
                "title": title,
                "date": start_date.strftime("%Y-%m-%d"),
                "location": location,
            }


def detect_year(events: List[Dict]) -> int:
    """
    Extract year from event dates.

    Args:
        events: List of event dictionaries

    Returns:
        The year that appears in the events (should be consistent per file)
    """
    if not events:
        raise ValueError("Cannot detect year from empty event list")

    # Get the year from the first event
    first_date = events[0]["date"]
    year = datetime.strptime(first_date, "%Y-%m-%d").year

    # Verify all events are from the same year
    for event in events:
        event_year = datetime.strptime(event["date"], "%Y-%m-%d").year
        if event_year != year:
            raise ValueError(f"Events contain multiple years: {year} and {event_year}")

    return year


def merge_events(
    new_events: List[Dict], existing_events: List[Dict], year: int
) -> List[Dict]:
    """
    Merge new events with existing events, replacing all events from the specified year.

    Args:
        new_events: Events from the new calendar file
        existing_events: Events from the existing calendar
        year: Year to replace (all events from this year will be removed)

    Returns:
        Merged list of events
    """
    # Filter out events from the specified year
    filtered_existing = [
        event
        for event in existing_events
        if datetime.strptime(event["date"], "%Y-%m-%d").year != year
    ]

    # Combine filtered existing events with new events
    merged_events = filtered_existing + new_events

    return merged_events
