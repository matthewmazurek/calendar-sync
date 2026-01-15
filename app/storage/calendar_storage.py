"""Calendar storage for file management."""

from pathlib import Path

from app.config import CalendarConfig
from app.models.metadata import CalendarWithMetadata
from app.output.base import CalendarWriter


class CalendarStorage:
    """File management for calendar storage."""

    def __init__(self, config: CalendarConfig | None = None):
        """Initialize storage with config."""
        self.config = config or CalendarConfig()

    def save_calendar(
        self,
        calendar_with_metadata: CalendarWithMetadata,
        writer: CalendarWriter,
        calendar_dir: Path,
    ) -> Path:
        """
        Save calendar using writer.

        Args:
            calendar_with_metadata: Calendar with metadata to save
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
        writer.write(calendar_with_metadata, filepath)

        return filepath
