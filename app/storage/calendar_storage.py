"""Calendar storage for file management."""

from pathlib import Path

from app.config import CalendarConfig
from app.models.calendar import Calendar
from app.output.base import CalendarWriter


class CalendarStorage:
    """File management for calendar storage."""

    def __init__(self, config: CalendarConfig | None = None):
        """Initialize storage with config."""
        self.config = config or CalendarConfig()

    def save_calendar(
        self,
        calendar: Calendar,
        writer: CalendarWriter,
        calendar_dir: Path,
    ) -> Path:
        """
        Save calendar using writer.

        Args:
            calendar: Calendar to save
            writer: CalendarWriter implementation
            calendar_dir: Directory to save in

        Returns:
            Path to saved file
        """
        calendar_dir.mkdir(parents=True, exist_ok=True)

        # Save as calendar.{ext} directly
        ext = writer.get_extension()
        filename = f"calendar.{ext}"
        filepath = calendar_dir / filename

        # Write using writer
        writer.write_calendar(calendar, filepath)

        return filepath
