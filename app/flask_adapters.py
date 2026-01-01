"""Adapter functions for Flask app to use new architecture."""

from datetime import date, datetime, time
from pathlib import Path
from typing import Dict, List, Optional

from app.ingestion.word_reader import WordReader
from app.models.calendar import Calendar
from app.models.event import Event
from app.output.ics_writer import ICSWriter
from app.processing.calendar_processor import CalendarProcessor
from app.storage.calendar_repository import CalendarRepository
from app.storage.calendar_storage import CalendarStorage


def dict_events_to_calendar(events: List[Dict]) -> Calendar:
    """
    Convert legacy Dict format events to Calendar model.

    Args:
        events: List of event dictionaries with keys:
            - title: str
            - date: str (YYYY-MM-DD format)
            - start: Optional[str] (HHMM format)
            - end: Optional[str] (HHMM format)
            - end_date: Optional[str] (YYYY-MM-DD format)
            - location: Optional[str]

    Returns:
        Calendar model
    """
    event_models = []
    for event_dict in events:
        # Parse date
        event_date = datetime.strptime(event_dict["date"], "%Y-%m-%d").date()

        # Parse optional times
        start_time = None
        if "start" in event_dict and event_dict["start"]:
            if isinstance(event_dict["start"], str):
                # HHMM format
                hour = int(event_dict["start"][:2])
                minute = int(event_dict["start"][2:])
                start_time = time(hour, minute)
            else:
                start_time = event_dict["start"]

        end_time = None
        if "end" in event_dict and event_dict["end"]:
            if isinstance(event_dict["end"], str):
                # HHMM format
                hour = int(event_dict["end"][:2])
                minute = int(event_dict["end"][2:])
                end_time = time(hour, minute)
            else:
                end_time = event_dict["end"]

        # Parse optional end_date
        end_date = None
        if "end_date" in event_dict and event_dict["end_date"]:
            if isinstance(event_dict["end_date"], str):
                end_date = datetime.strptime(event_dict["end_date"], "%Y-%m-%d").date()
            else:
                end_date = event_dict["end_date"]

        event = Event(
            title=event_dict["title"],
            date=event_date,
            start=start_time,
            end=end_time,
            end_date=end_date,
            location=event_dict.get("location"),
        )
        event_models.append(event)

    return Calendar(events=event_models)


def calendar_to_dict_events(calendar: Calendar) -> List[Dict]:
    """
    Convert Calendar model to legacy Dict format.

    Args:
        calendar: Calendar model

    Returns:
        List of event dictionaries
    """
    events = []
    for event in calendar.events:
        event_dict = {
            "title": event.title,
            "date": event.date.isoformat(),
        }
        if event.start:
            event_dict["start"] = event.start.strftime("%H%M")
        if event.end:
            event_dict["end"] = event.end.strftime("%H%M")
        if event.end_date:
            event_dict["end_date"] = event.end_date.isoformat()
        if event.location:
            event_dict["location"] = event.location
        events.append(event_dict)
    return events


def process_word_file_to_calendar(word_path: Path) -> Calendar:
    """
    Process a Word file and return a processed Calendar.

    Args:
        word_path: Path to Word file (.doc or .docx)

    Returns:
        Processed Calendar model
    """
    # Read using WordReader
    reader = WordReader()
    calendar = reader.read(word_path)

    # Process using CalendarProcessor
    processor = CalendarProcessor()
    processed_calendar, _ = processor.process(calendar)

    return processed_calendar


def calendar_to_ical_bytes(calendar: Calendar) -> bytes:
    """
    Convert Calendar model to iCalendar bytes.

    Args:
        calendar: Calendar model

    Returns:
        iCalendar content as bytes
    """
    writer = ICSWriter()
    # Use temporary path for writing (writer needs a path)
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".ics", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        writer.write(calendar, tmp_path)
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink()


def get_latest_calendar_bytes(
    repository: CalendarRepository, calendar_name: str = "latest"
) -> Optional[bytes]:
    """
    Get latest calendar file as bytes for Flask response.

    Args:
        repository: CalendarRepository instance
        calendar_name: Name of calendar to retrieve (default: "latest")

    Returns:
        Calendar bytes or None if not found
    """
    calendar_with_metadata = repository.load_calendar(calendar_name, format="ics")
    if calendar_with_metadata is None:
        return None

    return calendar_to_ical_bytes(calendar_with_metadata.calendar)
