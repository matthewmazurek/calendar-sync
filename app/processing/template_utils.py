"""Utility functions for template-based processing."""

from datetime import date, time
from typing import Literal

from app.models.event import Event
from app.models.template import TemplateSettings


def format_time(t: time, fmt: str = "12h") -> str:
    """Format time object to string format."""
    hour = t.hour
    minute = t.minute

    if fmt == "12h":
        period = "AM" if hour < 12 else "PM"
        if hour == 0:
            hour = 12
        elif hour > 12:
            hour -= 12
        return f"{hour}:{minute:02d} {period}"
    else:  # 24h
        return f"{hour:02d}:{minute:02d}"


def format_time_range(start: time, end: time, fmt: str = "12h", separator: str = " to ") -> str:
    """Format time range with separator."""
    start_str = format_time(start, fmt)
    end_str = format_time(end, fmt)
    return f"{start_str}{separator}{end_str}"


def format_title(
    template: str, event: Event, label: str | None, settings: TemplateSettings
) -> str:
    """Format title using template string with variables."""
    fmt = settings.time_format

    # Build variable map
    variables = {
        "title": event.title,
        "label": label.title() if label else "",
    }

    # Add time variables if event has times
    if event.start and event.end:
        variables["start"] = format_time(event.start, fmt)
        variables["end"] = format_time(event.end, fmt)
        variables["time_range"] = format_time_range(event.start, event.end, fmt)
    else:
        variables["start"] = ""
        variables["end"] = ""
        variables["time_range"] = ""

    # Replace variables in template
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))

    return result


def is_overnight(event: Event) -> bool:
    """Check if event spans midnight (start >= end)."""
    if event.start is None or event.end is None:
        return False
    return event.start >= event.end


def detect_shift_pattern(events: list[Event]) -> Literal["uniform_24h", "uniform_day", "mixed"]:
    """
    Detect shift pattern in a list of events.

    Returns:
        "uniform_24h" if all events are 24h (overnight)
        "uniform_day" if all events are day-only (not overnight)
        "mixed" if mix of both
    """
    if not events:
        return "uniform_day"

    overnight_count = sum(1 for e in events if is_overnight(e))
    total = len(events)

    if overnight_count == 0:
        return "uniform_day"
    elif overnight_count == total:
        return "uniform_24h"
    else:
        return "mixed"
