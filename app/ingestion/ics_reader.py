"""ICS file reader for calendar files."""

import logging
from datetime import date, timedelta
from pathlib import Path

from icalendar import Calendar

from app.exceptions import IngestionError
from app.ingestion.summary import build_ingestion_summary
from app.models.event import Event
from app.models.ingestion import IngestionResult, RawIngestion

logger = logging.getLogger(__name__)


class ICSReader:
    """Reader for ICS calendar files."""

    def read(self, path: Path) -> IngestionResult:
        """Read calendar from ICS file."""
        logger.info(f"Reading ICS file: {path}")
        try:
            if not path.exists():
                logger.warning(f"ICS file does not exist: {path}")
                raw = RawIngestion(events=[])
                return IngestionResult(raw=raw, summary=build_ingestion_summary(raw))

            # Check if file is empty
            if path.stat().st_size == 0:
                logger.warning(f"ICS file is empty: {path}")
                raw = RawIngestion(events=[])
                return IngestionResult(raw=raw, summary=build_ingestion_summary(raw))

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    logger.warning(f"ICS file contains only whitespace: {path}")
                    raw = RawIngestion(events=[])
                    return IngestionResult(raw=raw, summary=build_ingestion_summary(raw))
                cal = Calendar.from_ical(content)
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
        raw = RawIngestion(events=events)
        return IngestionResult(raw=raw, summary=build_ingestion_summary(raw))

    def _ics_event_to_dict(self, vevent) -> dict | None:
        """Convert an ICS VEVENT component to event dictionary."""
        # Extract title
        title = str(vevent.get("summary", ""))
        if not title:
            return None

        # Extract UID (unique identifier for upsert matching)
        uid = vevent.get("uid")
        uid_str = str(uid) if uid else None

        # Extract location
        location = str(vevent.get("location", "")) if vevent.get("location") else None
        if location == "":
            location = None

        # If location contains a newline (from previous round-trip with apple_title),
        # extract only the address part (after the newline)
        if location and "\n" in location:
            parts = location.split("\n", 1)
            if len(parts) == 2:
                # The second part is the actual address
                location = parts[1]

        # Extract geo coordinates
        geo = None
        geo_prop = vevent.get("geo")
        if geo_prop:
            try:
                # Geo can be a vGeo object with latitude/longitude attributes
                if hasattr(geo_prop, "latitude") and hasattr(geo_prop, "longitude"):
                    # vGeo object
                    geo = (float(geo_prop.latitude), float(geo_prop.longitude))
                elif isinstance(geo_prop, (tuple, list)) and len(geo_prop) == 2:
                    # Already a tuple
                    geo = (float(geo_prop[0]), float(geo_prop[1]))
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to parse geo coordinates: {e}")

        # Extract Apple structured location title
        apple_title = None
        apple_location = vevent.get("X-APPLE-STRUCTURED-LOCATION")
        if apple_location:
            try:
                # Extract X-TITLE parameter
                params = (
                    apple_location.params if hasattr(apple_location, "params") else {}
                )
                if "X-TITLE" in params:
                    apple_title = str(params["X-TITLE"])
            except (AttributeError, KeyError):
                pass

        # Extract start and end times
        dtstart = vevent.get("dtstart")
        dtend = vevent.get("dtend")

        if not dtstart:
            return None

        event_dict = {"title": title, "location": location}

        # Add uid if present
        if uid_str:
            event_dict["uid"] = uid_str

        # Add geo data if present
        if geo:
            event_dict["location_geo"] = geo
        if apple_title:
            event_dict["location_apple_title"] = apple_title

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
                    event_dict["end_date"] = (
                        actual_end_date - timedelta(days=1)
                    ).strftime("%Y-%m-%d")
            # else: single-day all-day event (no end_date needed)

        return event_dict
