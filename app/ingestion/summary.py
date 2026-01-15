"""Ingestion summary helpers for calendar data."""

from datetime import date, time, timedelta
from typing import Dict

from app.models.calendar import Calendar
from app.models.event import Event
from app.models.ingestion import IngestionSummary

NOON = time(12, 0)


def build_ingestion_summary(calendar: Calendar) -> IngestionSummary:
    """Build an ingestion summary for a calendar.

    Args:
        calendar: Source calendar to summarize.

    Returns:
        IngestionSummary with event counts, date range, and coverage stats.
    """
    if calendar.events:
        dates = [event.date for event in calendar.events]
        min_date = min(dates)
        max_date = max(dates)
        date_range = f"{min_date} to {max_date}"
    else:
        date_range = "no events"

    halfdays_booked: Dict[str, Dict[str, bool]] = {}
    for event in calendar.events:
        _apply_event_to_halfdays(halfdays_booked, event)

    total_halfdays = sum(
        1 for slots in halfdays_booked.values() for booked in slots.values() if booked
    )

    if halfdays_booked:
        weekly_coverage_year = len(halfdays_booked) / 52
    else:
        weekly_coverage_year = None

    return IngestionSummary(
        events=len(calendar.events),
        date_range=date_range,
        year=calendar.year,
        revised_date=calendar.revised_date,
        total_halfdays=total_halfdays,
        weekly_coverage_year=weekly_coverage_year,
    )


def _apply_event_to_halfdays(
    halfdays_booked: Dict[str, Dict[str, bool]], event: Event
) -> None:
    """Mark half-days booked for a single event."""
    if event.end_date and event.end_date > event.date:
        _mark_full_days(halfdays_booked, event.date, event.end_date)
        return

    if event.is_all_day:
        _mark_full_days(halfdays_booked, event.date, event.date)
        return

    start = event.start
    end = event.end
    if start is None or end is None:
        _mark_full_days(halfdays_booked, event.date, event.date)
        return

    _mark_timed_event(halfdays_booked, event.date, start, end)


def _mark_full_days(
    halfdays_booked: Dict[str, Dict[str, bool]],
    start_date: date,
    end_date: date,
) -> None:
    """Mark both AM and PM for all dates in the range."""
    current = start_date
    while current <= end_date:
        _ensure_date_entry(halfdays_booked, current)
        halfdays_booked[current.isoformat()]["AM"] = True
        halfdays_booked[current.isoformat()]["PM"] = True
        current += timedelta(days=1)


def _mark_timed_event(
    halfdays_booked: Dict[str, Dict[str, bool]],
    event_date: date,
    start_time: time,
    end_time: time,
) -> None:
    """Mark AM/PM for a timed event based on its time range."""
    _ensure_date_entry(halfdays_booked, event_date)
    if end_time <= NOON:
        halfdays_booked[event_date.isoformat()]["AM"] = True
    elif start_time >= NOON:
        halfdays_booked[event_date.isoformat()]["PM"] = True
    else:
        halfdays_booked[event_date.isoformat()]["AM"] = True
        halfdays_booked[event_date.isoformat()]["PM"] = True


def _ensure_date_entry(
    halfdays_booked: Dict[str, Dict[str, bool]],
    event_date: date,
) -> None:
    """Ensure date entry exists in halfdays_booked."""
    date_key = event_date.isoformat()
    if date_key not in halfdays_booked:
        halfdays_booked[date_key] = {"AM": False, "PM": False}
