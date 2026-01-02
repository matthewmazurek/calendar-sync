"""ICS file writer for calendar files."""

import uuid
from datetime import datetime, timedelta
from pathlib import Path

from icalendar import Alarm, Calendar, Event, vGeo, vText

from app.models.metadata import CalendarWithMetadata


class ICSWriter:
    """Writer for ICS calendar files."""

    def write(self, calendar_with_metadata: CalendarWithMetadata, path: Path) -> None:
        """Write calendar to ICS file."""
        calendar = calendar_with_metadata.calendar
        metadata = calendar_with_metadata.metadata

        cal = Calendar()
        cal.add("prodid", "-//Calendar Sync//EN")
        cal.add("version", "2.0")

        # Build calendar name from metadata and revision date
        base_name = metadata.name.title()
        revised_date = calendar.revised_date or metadata.source_revised_at
        if revised_date:
            calendar_name = f"{base_name} (Revised {revised_date})"
        else:
            calendar_name = base_name

        cal.add("X-WR-CALNAME", calendar_name)

        for event_model in calendar.events:
            event = Event()

            # Required fields
            event.add("summary", event_model.title)
            event.add("uid", str(uuid.uuid4()))
            event.add("dtstamp", datetime.now())

            # Add location if present
            if event_model.location:
                # Add geo information if available in event
                if event_model.location_geo and event_model.location_apple_title:
                    # Use vText to ensure proper escaping of newlines
                    combined_location = (
                        event_model.location_apple_title + "\n" + event_model.location
                    )
                    event["LOCATION"] = vText(combined_location)
                    event.add("geo", event_model.location_geo)
                    event.add(
                        "X-APPLE-STRUCTURED-LOCATION",
                        f"geo:{event_model.location_geo[0]},{event_model.location_geo[1]}",
                        parameters={
                            "VALUE": "URI",
                            "X-ADDRESS": event_model.location,
                            "X-APPLE-RADIUS": "49",
                            "X-TITLE": event_model.location_apple_title,
                        },
                    )
                else:
                    event.add("location", event_model.location)

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
        try:
            ical_content = cal.to_ical()
            if not ical_content:
                raise ValueError("Calendar.to_ical() returned empty content")

            with open(path, "wb") as f:
                f.write(ical_content)

            # Verify file was written
            if path.stat().st_size == 0:
                raise IOError(f"File was created but is empty: {path}")
        except Exception as e:
            # Remove empty file if it was created
            if path.exists() and path.stat().st_size == 0:
                try:
                    path.unlink()
                except OSError:
                    pass
            raise

    def get_extension(self) -> str:
        """Returns file extension."""
        return "ics"
