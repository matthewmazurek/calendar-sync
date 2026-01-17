"""Ingestion summary helpers for calendar data."""

from collections import defaultdict
from datetime import date, time, timedelta
from typing import Dict

from pydantic import BaseModel

from app.models.calendar import Calendar
from app.models.event import Event
from app.models.ingestion import IngestionSummary

NOON = time(12, 0)


class CalendarStatistics(BaseModel):
    """Detailed statistics for a calendar."""

    total_events: int
    date_range: str | None
    years: list[int]
    events_by_type: dict[str, int]
    events_by_year: dict[int, int]
    total_halfdays: int
    halfdays_by_week: dict[str, int]  # ISO week -> count
    weekly_coverage: float | None  # avg half days per week
    excluded_non_busy: int  # events excluded from coverage (busy=False)
    excluded_other_type: int  # events excluded from coverage (type='other')


def build_calendar_statistics(
    calendar: Calendar,
    year: int | None = None,
) -> CalendarStatistics:
    """Build detailed statistics for a calendar.

    Args:
        calendar: Calendar to analyze.
        year: Optional year to filter events by.

    Returns:
        CalendarStatistics with detailed event and coverage stats.
    """
    # Filter events by year if specified
    events = calendar.events
    if year is not None:
        events = [e for e in events if e.date.year == year]

    # Basic counts
    total_events = len(events)

    # Date range
    if events:
        dates = [e.date for e in events]
        min_date = min(dates)
        max_date = max(dates)
        date_range = f"{min_date} to {max_date}"
        years = sorted(set(d.year for d in dates))
    else:
        date_range = None
        years = []

    # Events by type (normalize to lowercase for consistency)
    events_by_type: dict[str, int] = defaultdict(int)
    for event in events:
        type_value = event.type or event.get_type_enum().value.lower()
        events_by_type[type_value] += 1

    # Events by year
    events_by_year: dict[int, int] = defaultdict(int)
    for event in events:
        events_by_year[event.date.year] += 1

    # Half days calculation (exclude "other" type events and busy=False events)
    halfdays_booked: Dict[str, Dict[str, bool]] = {}
    excluded_non_busy = 0
    excluded_other_type = 0
    for event in events:
        # Exclude busy=False events from coverage
        if not event.busy:
            excluded_non_busy += 1
            continue
        event_type = (event.type or event.get_type_enum().value).lower()
        if event_type == "other":
            excluded_other_type += 1
            continue
        _apply_event_to_halfdays(halfdays_booked, event)

    total_halfdays = sum(
        1 for slots in halfdays_booked.values() for booked in slots.values() if booked
    )

    # Half days by ISO week
    halfdays_by_week: dict[str, int] = defaultdict(int)
    for date_str, slots in halfdays_booked.items():
        event_date = date.fromisoformat(date_str)
        iso_year, iso_week, _ = event_date.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        halfdays_by_week[week_key] += sum(1 for booked in slots.values() if booked)

    # Weekly coverage (average half days per week)
    if halfdays_by_week:
        weekly_coverage = sum(halfdays_by_week.values()) / len(halfdays_by_week)
    else:
        weekly_coverage = None

    return CalendarStatistics(
        total_events=total_events,
        date_range=date_range,
        years=years,
        events_by_type=dict(events_by_type),
        events_by_year=dict(events_by_year),
        total_halfdays=total_halfdays,
        halfdays_by_week=dict(halfdays_by_week),
        weekly_coverage=weekly_coverage,
        excluded_non_busy=excluded_non_busy,
        excluded_other_type=excluded_other_type,
    )


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
