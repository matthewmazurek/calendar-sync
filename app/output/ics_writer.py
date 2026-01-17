"""ICS file writer for calendar files."""

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from icalendar import Alarm, Calendar, Event, vGeo, vText

from app.exceptions import ExportError
from app.models.metadata import CalendarWithMetadata

if TYPE_CHECKING:
    from app.models.template import CalendarTemplate


class ICSWriter:
    """Writer for ICS calendar files."""

    def write(
        self,
        calendar_with_metadata: CalendarWithMetadata,
        path: Path,
        template: "CalendarTemplate | None" = None,
    ) -> None:
        """Write calendar to ICS file.
        
        Args:
            calendar_with_metadata: Calendar with metadata to write
            path: Path to write ICS file
            template: Optional template for resolving location_id references
            
        Raises:
            ExportError: If location_id references a non-existent location in template
        """
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

            # Resolve location - either from location_id or direct location field
            location = event_model.location
            location_geo = event_model.location_geo
            location_apple_title = event_model.location_apple_title
            
            if event_model.location_id:
                # Resolve location_id from template
                if template is None:
                    raise ExportError(
                        f"Event '{event_model.title}' has location_id='{event_model.location_id}' "
                        f"but no template was provided for resolution. "
                        f"Either provide a template or use the 'location' field directly."
                    )
                
                location_config = template.locations.get(event_model.location_id)
                if location_config is None:
                    available = ", ".join(template.locations.keys()) or "(none)"
                    raise ExportError(
                        f"Event '{event_model.title}' references location_id='{event_model.location_id}' "
                        f"but this location is not defined in template '{template.name}'. "
                        f"Available locations: {available}"
                    )
                
                # Use resolved location data
                location = location_config.address
                location_geo = location_config.geo
                location_apple_title = location_config.apple_title

            # Add location if present
            if location:
                # Add geo information if available
                if location_geo and location_apple_title:
                    # Use vText to ensure proper escaping of newlines
                    combined_location = (
                        location_apple_title + "\n" + location
                    )
                    event["LOCATION"] = vText(combined_location)
                    event.add("geo", location_geo)
                    event.add(
                        "X-APPLE-STRUCTURED-LOCATION",
                        f"geo:{location_geo[0]},{location_geo[1]}",
                        parameters={
                            "VALUE": "URI",
                            "X-ADDRESS": location,
                            "X-APPLE-RADIUS": "49",
                            "X-TITLE": location_apple_title,
                        },
                    )
                else:
                    event.add("location", location)

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
