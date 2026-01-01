"""Calendar storage for file management."""

from pathlib import Path
from typing import Optional

from app.config import CalendarConfig
from app.output.base import CalendarWriter


class CalendarStorage:
    """File management for calendar storage."""

    def __init__(self, config: Optional[CalendarConfig] = None):
        """Initialize storage with config."""
        self.config = config or CalendarConfig()

    def save_calendar(
        self, calendar, writer: CalendarWriter, calendar_dir: Path, name: str
    ) -> Path:
        """
        Save calendar using writer.

        Args:
            calendar: Calendar to save
            writer: CalendarWriter implementation
            calendar_dir: Directory to save in
            name: Calendar name

        Returns:
            Path to saved file
        """
        calendar_dir.mkdir(parents=True, exist_ok=True)

        # Save as calendar.{ext} directly
        ext = writer.get_extension()
        filename = f"calendar.{ext}"
        filepath = calendar_dir / filename

        # Write using writer
        writer.write(calendar, filepath)

        return filepath
