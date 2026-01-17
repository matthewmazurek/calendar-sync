"""Calendar query module for filtering and selecting events."""

import re
from datetime import date, time, timedelta

from app.models.calendar import Calendar
from app.models.event import Event


class CalendarQuery:
    """Filter and select events from a calendar.

    Provides methods for common event filtering operations like
    getting today's events, upcoming events, or events within a date range.
    """

    def __init__(self, calendar: Calendar):
        """Initialize with a calendar.

        Args:
            calendar: Calendar to query events from.
        """
        self.events = calendar.events

    def search(
        self,
        query: str | None = None,
        event_type: str | None = None,
        location: str | None = None,
    ) -> list[Event]:
        """Search events by text, type, or location.

        All criteria are combined with AND logic. Text search is
        case-insensitive and matches against event title.

        Args:
            query: Text to search for in event titles.
            event_type: Filter by event type (case-insensitive).
            location: Filter by location (case-insensitive, partial match).

        Returns:
            List of matching events, sorted by date and time.
        """
        matching = list(self.events)

        # Filter by text query (title)
        if query:
            query_lower = query.lower()
            matching = [e for e in matching if query_lower in e.title.lower()]

        # Filter by event type
        if event_type:
            type_lower = event_type.lower()
            matching = [
                e for e in matching
                if (e.type and e.type.lower() == type_lower)
                or (not e.type and type_lower == "other")
            ]

        # Filter by location
        if location:
            location_lower = location.lower()
            matching = [
                e for e in matching
                if (e.location and location_lower in e.location.lower())
                or (e.location_id and location_lower in e.location_id.lower())
            ]

        return self._sort_by_date_time(matching)

    def today(self, ref_date: date | None = None) -> list[Event]:
        """Get events for today.

        Args:
            ref_date: Reference date (defaults to today).

        Returns:
            List of events occurring today, sorted by start time.
        """
        target = ref_date or date.today()
        return self.on_date(target)

    def on_date(self, target: date) -> list[Event]:
        """Get events on a specific date.

        Includes events that start on this date, as well as multi-day
        events that span across this date.

        Args:
            target: The date to filter events for.

        Returns:
            List of events occurring on the target date, sorted by start time.
        """
        matching = []
        for event in self.events:
            # Event starts on this date
            if event.date == target:
                matching.append(event)
            # Multi-day event spans this date
            elif event.end_date and event.date < target <= event.end_date:
                matching.append(event)
        return self._sort_by_time(matching)

    def upcoming(self, days: int = 7, ref_date: date | None = None) -> list[Event]:
        """Get events in the next N days.

        Args:
            days: Number of days to look ahead (default: 7).
            ref_date: Reference date (defaults to today).

        Returns:
            List of events in the date range, sorted by date and time.
        """
        start = ref_date or date.today()
        end = start + timedelta(days=days - 1)
        return self.date_range(start, end)

    def date_range(self, start: date, end: date) -> list[Event]:
        """Get events within a date range (inclusive).

        Args:
            start: Start date (inclusive).
            end: End date (inclusive).

        Returns:
            List of events within the range, sorted by date and time.
        """
        matching = []
        for event in self.events:
            # Event starts within range
            if start <= event.date <= end:
                matching.append(event)
            # Multi-day event starts before range but extends into it
            elif event.end_date and event.date < start <= event.end_date:
                matching.append(event)
        return self._sort_by_date_time(matching)

    def by_year(self, year: int) -> list[Event]:
        """Get events for a specific year.

        Args:
            year: The year to filter by.

        Returns:
            List of events in that year, sorted by date and time.
        """
        matching = [e for e in self.events if e.date.year == year]
        return self._sort_by_date_time(matching)

    def all(self) -> list[Event]:
        """Get all events, sorted by date and time.

        Returns:
            All events in the calendar, sorted.
        """
        return self._sort_by_date_time(list(self.events))

    def _sort_by_time(self, events: list[Event]) -> list[Event]:
        """Sort events by start time (all-day events first)."""
        return sorted(events, key=lambda e: (e.start or time.min,))

    def _sort_by_date_time(self, events: list[Event]) -> list[Event]:
        """Sort events by date, then by start time."""
        return sorted(events, key=lambda e: (e.date, e.start or time.min))
