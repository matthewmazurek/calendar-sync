"""Diff renderer for calendar comparison display."""

from datetime import time

from app.models.calendar import Calendar
from app.models.event import Event
from cli.display.console import console

# Used for sorting events without a start time (all-day events sort to beginning of day)
_SORT_TIME_FALLBACK = time(0, 0)


class DiffRenderer:
    """Render calendar diff output.

    Displays added, removed, and modified events with color-coded output.
    """

    def format_event_summary(self, event: Event) -> str:
        """Format an event for display.

        Args:
            event: Event to format.

        Returns:
            Formatted string like "2026-01-17 08:00-12:00: Event Title".
        """
        date_str = event.date.strftime("%Y-%m-%d")
        time_str = ""
        if event.start:
            time_str = f" {event.start.strftime('%H:%M')}"
            if event.end:
                time_str += f"-{event.end.strftime('%H:%M')}"
        return f"{date_str}{time_str}: {event.title}"

    def render_diff(
        self,
        added: list[Event],
        removed: list[Event],
        modified: list[tuple[Event, Event]],
        old_label: str = "before",
        new_label: str = "after",
        compact: bool = False,
        show_stats: bool = False,
    ) -> bool:
        """Render diff output between two calendar states.

        Args:
            added: List of added events.
            removed: List of removed events.
            modified: List of (old_event, new_event) tuples for modified events.
            old_label: Label for the old version.
            new_label: Label for the new version.
            compact: If True, only show counts.
            show_stats: If True, show statistics summary before detailed output.

        Returns:
            True if there were differences, False otherwise.
        """
        total_changes = len(added) + len(removed) + len(modified)
        if total_changes == 0:
            console.print("No differences.")
            return False

        # Header
        console.print(f"\nChanges ({old_label} → {new_label}):")
        console.print()

        # Stats or compact mode - show counts
        if compact or show_stats:
            self._render_counts(added, removed, modified)
            if compact:
                return True
            console.print()

        # Detailed output
        self._render_added(added)
        self._render_removed(removed)
        self._render_modified(modified)

        # Summary line (if not in stats mode)
        if not show_stats:
            self._render_summary_line(added, removed, modified)

        return True

    def render_comparison_header(
        self,
        calendar_name: str,
        display1: str,
        display2: str,
    ) -> None:
        """Render the header for a version comparison.

        Args:
            calendar_name: Name of the calendar being compared.
            display1: Display name for the first version.
            display2: Display name for the second version.
        """
        console.print(f"Comparing calendar '{calendar_name}':")
        console.print(f"  {display1} → {display2}")
        console.print()

    def render_no_differences(self) -> None:
        """Render message when no differences are found."""
        console.print("No differences found.")

    def render_same_version(self, display_name: str) -> None:
        """Render message when comparing same version.

        Args:
            display_name: Display name of the version.
        """
        console.print(f"Comparing {display_name} with itself - no differences.")

    def _render_counts(
        self,
        added: list[Event],
        removed: list[Event],
        modified: list[tuple[Event, Event]],
    ) -> None:
        """Render the change counts."""
        total_changes = len(added) + len(removed) + len(modified)
        console.print(f"  Added:    {len(added):>4} event(s)")
        console.print(f"  Removed:  {len(removed):>4} event(s)")
        console.print(f"  Modified: {len(modified):>4} event(s)")
        console.print("  ─────────────────")
        console.print(f"  Total:    {total_changes:>4} change(s)")

    def _render_added(self, added: list[Event]) -> None:
        """Render added events section."""
        if not added:
            return

        console.print("[bold green]Added events:[/bold green]")
        for event in sorted(added, key=lambda e: (e.date, e.start or _SORT_TIME_FALLBACK)):
            summary = self.format_event_summary(event)
            console.print(f"[green]  + {summary}[/green]")
        console.print()

    def _render_removed(self, removed: list[Event]) -> None:
        """Render removed events section."""
        if not removed:
            return

        console.print("[bold red]Removed events:[/bold red]")
        for event in sorted(removed, key=lambda e: (e.date, e.start or _SORT_TIME_FALLBACK)):
            summary = self.format_event_summary(event)
            console.print(f"[red]  - {summary}[/red]")
        console.print()

    def _render_modified(self, modified: list[tuple[Event, Event]]) -> None:
        """Render modified events section."""
        if not modified:
            return

        # Exclude computed fields from comparison
        exclude = {"is_all_day", "is_overnight"}

        console.print("[bold yellow]Modified events:[/bold yellow]")
        for old_event, new_event in sorted(
            modified, key=lambda x: (x[1].date, x[1].start or _SORT_TIME_FALLBACK)
        ):
            summary = self.format_event_summary(new_event)
            console.print(f"[yellow]  ~ {summary}[/yellow]")

            # Show what changed - compare all fields dynamically
            old_dict = old_event.model_dump(exclude=exclude)
            new_dict = new_event.model_dump(exclude=exclude)

            for field in old_dict:
                old_val = old_dict[field]
                new_val = new_dict[field]
                if old_val != new_val:
                    # Format values for display
                    old_str = self._format_field_value(old_val)
                    new_str = self._format_field_value(new_val)
                    console.print(f"      {field}: {old_str} → {new_str}")
        console.print()

    def _format_field_value(self, value) -> str:
        """Format a field value for display in diff output."""
        if value is None:
            return "none"
        if hasattr(value, "strftime"):
            # Handle date/time objects
            if hasattr(value, "hour"):
                return value.strftime("%H:%M")
            return str(value)
        if isinstance(value, tuple):
            # Handle geo coordinates
            return f"({value[0]:.6f}, {value[1]:.6f})"
        return str(value)

    def _render_summary_line(
        self,
        added: list[Event],
        removed: list[Event],
        modified: list[tuple[Event, Event]],
    ) -> None:
        """Render the summary line with colored counts."""
        summary_parts = []
        if added:
            summary_parts.append(f"[green]+{len(added)}[/green]")
        if removed:
            summary_parts.append(f"[red]-{len(removed)}[/red]")
        if modified:
            summary_parts.append(f"[yellow]~{len(modified)}[/yellow]")
        console.print(f"Summary: {', '.join(summary_parts)}")
