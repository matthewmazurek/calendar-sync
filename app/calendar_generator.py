import uuid
from datetime import datetime, timedelta
from typing import Dict, List

from icalendar import Alarm, Calendar, Event, vGeo, vText

from app.event_processor import WORK_LOCATION


def generate_ical(events: List[Dict]) -> Calendar:
    """
    Convert a list of event dictionaries into an iCalendar object.

    Args:
        events: List of event dictionaries, each containing:
            - title: Event title
            - date: YYYY-MM-DD format
            - start: Optional, HHMM format
            - end: Optional, HHMM format
            - end_date: Optional, YYYY-MM-DD format for multi-day events
            - location: Optional, location string

    Returns:
        An icalendar.Calendar object containing all events
    """
    cal = Calendar()
    cal.add("prodid", "-//Calendar Sync//EN")
    cal.add("version", "2.0")

    for event_dict in events:
        event = Event()

        # Required fields
        event.add("summary", event_dict["title"])
        event.add("uid", str(uuid.uuid4()))
        event.add("dtstamp", datetime.now())

        # Add location if present
        if "location" in event_dict:
            event.add("location", event_dict["location"])
            # Normalize LOCATION property
            event["LOCATION"] = event_dict["location"]

            # Add geo information for work location
            if event_dict["location"] == WORK_LOCATION:
                # Override LOCATION to include name and full address on separate lines for Apple Maps
                event["LOCATION"] = (
                    "Foothills Medical Centre\n1403 29 St NW, Calgary AB T2N 2T9, Canada"
                )
                # Add GEO property (RFC 5545)
                event.add("geo", (51.065389, -114.133306))
                # Add Apple structured location
                event.add(
                    "X-APPLE-STRUCTURED-LOCATION",
                    "geo:51.065389,-114.133306",
                    parameters={
                        "VALUE": "URI",
                        "X-ADDRESS": "1403 29 St NW, Calgary AB T2N 2T9, Canada",
                        "X-APPLE-RADIUS": "49",
                        "X-TITLE": "Foothills Medical Centre",
                    },
                )

        # Parse date
        date = datetime.strptime(event_dict["date"], "%Y-%m-%d")

        if "end_date" in event_dict:
            # Multi-day event
            end_date = datetime.strptime(event_dict["end_date"], "%Y-%m-%d")
            if "start" in event_dict and "end" in event_dict:
                # Multi-day timed event
                start_time = datetime.strptime(event_dict["start"], "%H%M").time()
                end_time = datetime.strptime(event_dict["end"], "%H%M").time()

                start_dt = datetime.combine(date.date(), start_time)
                end_dt = datetime.combine(end_date.date(), end_time)

                event.add("dtstart", start_dt)
                event.add("dtend", end_dt)
            else:
                # Multi-day all-day event
                event.add("dtstart", date.date())
                # End date is exclusive in iCalendar, so add one day
                event.add("dtend", (end_date + timedelta(days=1)).date())
        else:
            # Single-day event
            if "start" in event_dict and "end" in event_dict:
                # Timed event
                start_time = datetime.strptime(event_dict["start"], "%H%M").time()
                end_time = datetime.strptime(event_dict["end"], "%H%M").time()

                start_dt = datetime.combine(date.date(), start_time)
                end_dt = datetime.combine(date.date(), end_time)

                event.add("dtstart", start_dt)
                event.add("dtend", end_dt)
            else:
                # All-day event
                event.add("dtstart", date.date())
                # All-day events end on the next day
                event.add("dtend", (date + timedelta(days=1)).date())

        cal.add_component(event)

    ical_bytes = cal.to_ical()
    # print(f"DEBUG: iCal output: {ical_bytes[:200]!r}")
    return cal
