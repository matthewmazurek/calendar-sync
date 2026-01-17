"""Event renderer protocol for display abstraction."""

from typing import Protocol

from app.models.event import Event


class EventRenderer(Protocol):
    """Protocol for rendering calendar events.

    Implementations of this protocol can render events in different
    formats (Rich terminal, plain text, HTML, etc.) while maintaining
    a consistent interface.
    """

    def render_agenda(
        self,
        events: list[Event],
        title: str | None = None,
        subtitle: str | None = None,
    ) -> None:
        """Render events grouped by day (agenda view).

        Events are grouped by date with relative date labels
        (TODAY, Tomorrow, weekday names).

        Args:
            events: List of events to render (should be sorted by date/time).
            title: Optional title for the display header.
            subtitle: Optional subtitle (e.g., date range info).
        """
        ...

    def render_list(
        self,
        events: list[Event],
        title: str | None = None,
        subtitle: str | None = None,
    ) -> None:
        """Render events as a flat list.

        Each event is displayed on its own line with date, time,
        title, and location. Ideal for search results.

        Args:
            events: List of events to render (should be sorted by date/time).
            title: Optional title for the display header.
            subtitle: Optional subtitle (e.g., search query info).
        """
        ...

    def render_empty(self, message: str | None = None) -> None:
        """Render an empty state message.

        Args:
            message: Optional custom message (defaults to "No events found").
        """
        ...
