"""ICS file reader for calendar files."""

import logging
from datetime import date, timedelta
from pathlib import Path

from icalendar import Calendar

from app.exceptions import IngestionError
from app.models.calendar import Calendar as CalendarModel
from app.models.event import Event

logger = logging.getLogger(__name__)


class ICSReader:
    """Reader for ICS calendar files."""

    def read(self, path: Path) -> CalendarModel:
        """Read calendar from ICS file."""
        logger.info(f"Reading ICS file: {path}")
        try:
            if not path.exists():
                logger.warning(f"ICS file does not exist: {path}")
                return CalendarModel(events=[])

            with open(path, "r", encoding="utf-8") as f:
                cal = Calendar.from_ical(f.read())
        except Exception as e:
            raise IngestionError(f"Failed to read ICS file: {e}") from e

        events = []

        for component in cal.walk():
            if component.name == "VEVENT":
                event_dict = self._ics_event_to_dict(component)
                if event_dict:
                    try:
                        events.append(Event(**event_dict))
                    except Exception as e:
                        raise IngestionError(
                            f"Failed to create event from ICS component: {e}"
                        ) from e

        logger.info(f"Created {len(events)} events from ICS file")
        return CalendarModel(events=events)

    def _ics_event_to_dict(self, vevent) -> dict | None:
        """Convert an ICS VEVENT component to event dictionary."""
        # Extract title
        title = str(vevent.get("summary", ""))
        if not title:
            return None

        # Extract location
        location = str(vevent.get("location", "")) if vevent.get("location") else None
        if location == "":
            location = None

        # Extract start and end times
        dtstart = vevent.get("dtstart")
        dtend = vevent.get("dtend")

        if not dtstart:
            return None

        event_dict = {"title": title, "location": location}

        # Convert dtstart to datetime object
        if hasattr(dtstart.dt, "date") and hasattr(dtstart.dt, "time"):
            # It's a datetime (timed event)
            start_dt = dtstart.dt
            start_date = start_dt.date()
            start_time = start_dt.time()

            event_dict["date"] = start_date.strftime("%Y-%m-%d")
            event_dict["start"] = start_time.strftime("%H%M")

            # Check if it's a multi-day event
            if dtend:
                if hasattr(dtend.dt, "date") and hasattr(dtend.dt, "time"):
                    # dtend is also a datetime
                    end_dt = dtend.dt
                    end_date = end_dt.date()
                    end_time = end_dt.time()

                    event_dict["end"] = end_time.strftime("%H%M")

                    if start_date != end_date:
                        # Multi-day timed event
                        event_dict["end_date"] = end_date.strftime("%Y-%m-%d")
                else:
                    # dtend is a date (shouldn't happen with timed events, but handle it)
                    end_date = dtend.dt
                    event_dict["end"] = start_time.strftime("%H%M")
            else:
                # No dtend, single-day timed event
                event_dict["end"] = start_time.strftime("%H%M")
        else:
            # It's a date (all-day event)
            start_date = dtstart.dt

            event_dict["date"] = start_date.strftime("%Y-%m-%d")

            if dtend:
                end_date = dtend.dt
                # For all-day events, dtend is exclusive, so subtract 1 day
                if isinstance(end_date, date):
                    actual_end_date = end_date
                else:
                    actual_end_date = end_date.date()

                # Check if it's multi-day (accounting for the +1 day in dtend)
                if actual_end_date == start_date + timedelta(days=1):
                    # Single-day all-day event
                    pass
                else:
                    # Multi-day all-day event
                    event_dict["end_date"] = (actual_end_date - timedelta(days=1)).strftime(
                        "%Y-%m-%d"
                    )
            # else: single-day all-day event (no end_date needed)

        return event_dict
