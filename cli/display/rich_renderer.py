"""Rich-based event renderer for terminal display."""

from collections import defaultdict
from datetime import date, time

from rich.console import Console
from rich.text import Text

from app.models.event import Event
from cli.display.console import console as shared_console


class RichEventRenderer:
    """Render calendar events using Rich for terminal display.

    Uses neutral hierarchy-based colors:
    - Headers: bold white
    - Date/day labels: cyan
    - Times: dim
    - Event titles: default (white/normal)
    - Locations: dim italic
    - Metadata (overnight, all-day): dim
    """

    def __init__(self, console: Console | None = None):
        """Initialize the renderer.

        Args:
            console: Rich Console instance (uses shared console if not provided).
        """
        self.console = console or shared_console

    def render_agenda(
        self,
        events: list[Event],
        title: str | None = None,
        subtitle: str | None = None,
    ) -> None:
        """Render events grouped by day (agenda view).

        Args:
            events: List of events to render (should be sorted by date/time).
            title: Optional title for the display header.
            subtitle: Optional subtitle (e.g., date range info).
        """
        if not events:
            self.render_empty()
            return

        # Print header
        self._print_header(title, subtitle)

        # Group events by date
        by_date: dict[date, list[Event]] = defaultdict(list)
        for event in events:
            by_date[event.date].append(event)

        today = date.today()

        # Render each day group
        for event_date in sorted(by_date.keys()):
            day_events = by_date[event_date]

            # Format day header
            day_label = self._format_day_label(event_date, today)
            self.console.print(f"\n[cyan]{day_label}[/cyan]")

            # Render each event
            for event in day_events:
                self._render_agenda_event(event)

        # Print footer
        self._print_footer(len(events))

    def render_list(
        self,
        events: list[Event],
        title: str | None = None,
        subtitle: str | None = None,
    ) -> None:
        """Render events as a flat list.

        Args:
            events: List of events to render (should be sorted by date/time).
            title: Optional title for the display header.
            subtitle: Optional subtitle (e.g., search query info).
        """
        if not events:
            self.render_empty()
            return

        # Print header
        self._print_header(title, subtitle)
        self.console.print()

        # Render each event as a single line
        for event in events:
            self._render_list_event(event)

        # Print footer
        self._print_footer(len(events))

    def render_empty(self, message: str | None = None) -> None:
        """Render an empty state message.

        Args:
            message: Optional custom message (defaults to "No events found").
        """
        msg = message or "No events found"
        self.console.print(f"\n[dim]{msg}[/dim]\n")

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _print_header(self, title: str | None, subtitle: str | None) -> None:
        """Print the display header."""
        self.console.print()
        self.console.print("━" * 40)
        if title:
            header_text = f"  {title}"
            if subtitle:
                header_text += f" [dim]({subtitle})[/dim]"
            self.console.print(f"[bold]{header_text}[/bold]")
        self.console.print("━" * 40)

    def _print_footer(self, count: int) -> None:
        """Print the display footer with event count."""
        self.console.print()
        self.console.print("─" * 40)
        event_word = "event" if count == 1 else "events"
        self.console.print(f"[dim]{count} {event_word}[/dim]")
        self.console.print()

    def _format_day_label(self, event_date: date, today: date) -> str:
        """Format a date as a human-readable day label.

        Args:
            event_date: The date to format.
            today: Today's date for relative comparison.

        Returns:
            Formatted string like "TODAY (Thu Jan 16)" or "Mon Jan 19".
        """
        delta = (event_date - today).days

        if delta == 0:
            return f"TODAY ({event_date.strftime('%a %b %d')})"
        elif delta == 1:
            return f"Tomorrow ({event_date.strftime('%a %b %d')})"
        elif delta == -1:
            return f"Yesterday ({event_date.strftime('%a %b %d')})"
        else:
            return event_date.strftime("%a %b %d")

    def _format_time_range(self, event: Event) -> str:
        """Format the time range for an event.

        Args:
            event: The event to format.

        Returns:
            Formatted time string like "08:00–12:00" or "All day".
        """
        if event.is_all_day:
            return "All day"

        parts = []
        if event.start:
            parts.append(event.start.strftime("%H:%M"))
        if event.end:
            parts.append(event.end.strftime("%H:%M"))

        return "–".join(parts) if parts else ""

    def _format_overnight_indicator(self, event: Event) -> str | None:
        """Format an overnight indicator if applicable.

        Args:
            event: The event to check.

        Returns:
            String like "→ Thu" or None if not overnight.
        """
        if event.is_overnight and event.end_date:
            return f"→ {event.end_date.strftime('%a')}"
        return None

    def _render_agenda_event(self, event: Event) -> None:
        """Render a single event in agenda format."""
        # Time column (fixed width for alignment)
        time_str = self._format_time_range(event)
        overnight = self._format_overnight_indicator(event)
        location = self._get_display_location(event)

        # Build the event line
        line = Text()
        line.append("  ")
        line.append(f"{time_str:<12}", style="dim")
        line.append(f"{event.title:<16}")

        if location:
            line.append(f" ({location})", style="dim")

        if overnight:
            line.append(f" {overnight}", style="dim")

        self.console.print(line)

    def _render_list_event(self, event: Event) -> None:
        """Render a single event in list format."""
        date_str = event.date.strftime("%Y-%m-%d")
        day_str = event.date.strftime("%a")
        time_str = self._format_time_range(event)
        overnight = self._format_overnight_indicator(event)
        location = self._get_display_location(event)

        # Build the line with color hierarchy:
        # - Date: dim (background context)
        # - Day: magenta (orientation helper)
        # - Time: blue (secondary info)
        # - Title: default (primary focus)
        # - Location: dim italic (context)
        # - Overnight: magenta (callout)
        line = Text()
        line.append(f"{date_str}  ", style="dim")
        line.append(f"{day_str}  ", style="cyan")
        line.append(f"{time_str:<12}", style="blue")
        line.append(event.title)

        if location:
            line.append(f" ({location})", style="italic dim")

        if overnight:
            line.append(f" {overnight}", style="cyan")

        self.console.print(line)

    def _get_display_location(self, event: Event) -> str | None:
        """Get the display location for an event.

        Args:
            event: The event to get location from.

        Returns:
            Location string or None if no location set.
        """
        # Prefer resolved location, fall back to location_id
        if event.location:
            return event.location
        if event.location_id:
            return event.location_id
        return None
