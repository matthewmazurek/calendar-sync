"""ICS file writer for calendar files."""

import uuid
from datetime import datetime, timedelta
from pathlib import Path

from icalendar import Alarm, Calendar, Event, vGeo, vText

from app.models.calendar import Calendar as CalendarModel
from app.models.event import Event as EventModel

WORK_LOCATION = "Foothills Medical Centre, 1403 29 St NW, Calgary AB T2N 2T9, Canada"


class ICSWriter:
    """Writer for ICS calendar files."""

    def write(self, calendar: CalendarModel, path: Path) -> None:
        """Write calendar to ICS file."""
        cal = Calendar()
        cal.add("prodid", "-//Calendar Sync//EN")
        cal.add("version", "2.0")

        # Add revised date if present
        if calendar.revised_date:
            cal.add("X-WR-CALNAME", f"Calendar (Revised {calendar.revised_date})")

        for event_model in calendar.events:
            event = Event()

            # Required fields
            event.add("summary", event_model.title)
            event.add("uid", str(uuid.uuid4()))
            event.add("dtstamp", datetime.now())

            # Add location if present
            if event_model.location:
                event.add("location", event_model.location)
                event["LOCATION"] = event_model.location

                # Add geo information for work location
                if event_model.location == WORK_LOCATION:
                    event["LOCATION"] = (
                        "Foothills Medical Centre\n1403 29 St NW, Calgary AB T2N 2T9, Canada"
                    )
                    event.add("geo", (51.065389, -114.133306))
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

            # Convert time objects back to datetime
            date = datetime.combine(event_model.date, datetime.min.time())

            if event_model.end_date:
                # Multi-day event
                end_date = datetime.combine(event_model.end_date, datetime.min.time())
                if event_model.start and event_model.end:
                    # Multi-day timed event
                    start_dt = datetime.combine(event_model.date, event_model.start)
                    end_dt = datetime.combine(event_model.end_date, event_model.end)
                    event.add("dtstart", start_dt)
                    event.add("dtend", end_dt)
                else:
                    # Multi-day all-day event
                    event.add("dtstart", event_model.date)
                    # End date is exclusive in iCalendar, so add one day
                    event.add("dtend", (event_model.end_date + timedelta(days=1)))
            else:
                # Single-day event
                if event_model.start and event_model.end:
                    # Timed event
                    start_dt = datetime.combine(event_model.date, event_model.start)
                    end_dt = datetime.combine(event_model.date, event_model.end)
                    event.add("dtstart", start_dt)
                    event.add("dtend", end_dt)
                else:
                    # All-day event
                    event.add("dtstart", event_model.date)
                    # All-day events end on the next day
                    event.add("dtend", (event_model.date + timedelta(days=1)))

            cal.add_component(event)

        # Write to file
        with open(path, "wb") as f:
            f.write(cal.to_ical())

    def get_extension(self) -> str:
        """Returns file extension."""
        return "ics"
