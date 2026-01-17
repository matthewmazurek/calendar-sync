"""Stats renderer for calendar statistics display."""

from app.ingestion.summary import CalendarStatistics
from cli.display.console import console


class StatsRenderer:
    """Render calendar statistics.

    Displays event counts, coverage metrics, and scheduling patterns
    with optional weekly breakdown charts.
    """

    def render_statistics(
        self,
        stats_data: CalendarStatistics,
        calendar_name: str,
        year: int | None = None,
        show_weeks: bool = False,
    ) -> None:
        """Render full statistics display.

        Args:
            stats_data: CalendarStatistics object with computed stats.
            calendar_name: Name of the calendar.
            year: Optional year filter (for header display).
            show_weeks: Whether to show weekly breakdown.
        """
        self._render_header(calendar_name, year)
        self._render_overview(stats_data)
        self._render_events_by_type(stats_data)
        self._render_events_by_year(stats_data, year)
        self._render_coverage(stats_data)

        if show_weeks:
            self._render_weekly_breakdown(stats_data)

        console.print()  # trailing newline

    def _render_header(self, calendar_name: str, year: int | None) -> None:
        """Render the statistics header."""
        year_label = f" ({year})" if year else ""
        console.print()
        console.print("━" * 50)
        console.print(f"[bold]  Statistics: {calendar_name}{year_label}[/bold]")
        console.print("━" * 50)

    def _render_overview(self, stats_data: CalendarStatistics) -> None:
        """Render the overview section."""
        console.print("\n[bold]Overview:[/bold]")
        console.print(f"  Events: {stats_data.total_events:,}")
        if stats_data.date_range:
            console.print(f"  Date range: {stats_data.date_range}")
        if len(stats_data.years) > 1:
            console.print(f"  Years: {', '.join(str(y) for y in stats_data.years)}")

    def _render_events_by_type(self, stats_data: CalendarStatistics) -> None:
        """Render events by type section."""
        if not stats_data.events_by_type:
            return

        console.print("\n[bold]Events by Type:[/bold]")
        max_type_len = max(len(t) for t in stats_data.events_by_type.keys())

        for event_type, count in sorted(
            stats_data.events_by_type.items(), key=lambda x: -x[1]
        ):
            pct = (
                (count / stats_data.total_events) * 100
                if stats_data.total_events
                else 0
            )
            console.print(
                f"  {event_type:<{max_type_len}}  {count:>4}  [dim]({pct:>5.1f}%)[/dim]"
            )

    def _render_events_by_year(
        self, stats_data: CalendarStatistics, year_filter: int | None
    ) -> None:
        """Render events by year section (only if multi-year and no filter)."""
        if year_filter is not None or len(stats_data.events_by_year) <= 1:
            return

        console.print("\n[bold]Events by Year:[/bold]")
        for y, count in sorted(stats_data.events_by_year.items()):
            console.print(f"  {y}: {count:,}")

    def _render_coverage(self, stats_data: CalendarStatistics) -> None:
        """Render coverage statistics section."""
        console.print(
            "\n[bold]Coverage[/bold] [dim](excluding 'other' type events):[/dim]"
        )
        if stats_data.excluded_events > 0:
            console.print(
                f"  [dim]Excluded {stats_data.excluded_events} non-busy events "
                "(holidays, vacation)[/dim]"
            )
        console.print(f"  Total half-days booked: {stats_data.total_halfdays}")
        if stats_data.weekly_coverage is not None:
            console.print(
                f"  Average per week: {stats_data.weekly_coverage:.1f} half-days"
            )
        weeks_with_events = len(stats_data.halfdays_by_week)
        console.print(f"  Weeks with events: {weeks_with_events}")

    def _render_weekly_breakdown(self, stats_data: CalendarStatistics) -> None:
        """Render weekly breakdown with bar charts."""
        if not stats_data.halfdays_by_week:
            return

        console.print("\n[bold]Half-days by Week:[/bold]")
        for week_key, count in sorted(stats_data.halfdays_by_week.items()):
            # Build bar: solid for count, ░ to fill to 10, dim ░ to fill to 14
            solid = "█" * min(count, 14)
            mid = "░" * max(0, 10 - count)
            light = "░" * max(0, 14 - max(count, 10))
            bar = f"[cyan]{solid}{mid}[/cyan][dim]{light}[/dim]"
            console.print(f"  {week_key}: {bar} {count}")

    def render_not_found(self, calendar_name: str) -> None:
        """Render calendar not found message.

        Args:
            calendar_name: Name of the calendar that wasn't found.
        """
        console.print(f"\nCalendar '{calendar_name}' not found")
