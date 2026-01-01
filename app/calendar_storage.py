import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Default calendar directory
DEFAULT_CALENDAR_DIR = Path("data/calendars")
# Default retention period in days
DEFAULT_RETENTION_DAYS = 365


def save_calendar(ical_content: bytes, path: str | None = None) -> str:
    """
    Save a calendar file with timestamp and return the filename.

    Args:
        ical_content: The iCalendar content as bytes
        path: The path to save the calendar file, if not provided, the calendar will be saved in the default calendar directory

    Returns:
        The filename of the saved calendar
    """
    # Use provided path or default directory
    if path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(ical_content)
        return path

    # If no path provided, use default directory with timestamp
    calendar_dir = DEFAULT_CALENDAR_DIR
    calendar_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"calendar_{timestamp}.ics"
    filepath = calendar_dir / filename

    # Save the file
    with open(filepath, "wb") as f:
        f.write(ical_content)

    # Update the latest file by copying
    latest_path = calendar_dir / "latest-calendar.ics"
    if latest_path.exists():
        latest_path.unlink()
    shutil.copy2(filepath, latest_path)

    # Clean up old files
    cleanup_old_calendars(calendar_dir)

    return filename


def cleanup_old_calendars(calendar_dir: Path = DEFAULT_CALENDAR_DIR):
    """Remove calendar files older than the retention period."""
    if not calendar_dir.exists():
        return

    cutoff_date = datetime.now() - timedelta(days=DEFAULT_RETENTION_DAYS)

    for file in calendar_dir.glob("calendar_*.ics"):
        try:
            # Extract timestamp from filename
            timestamp_str = file.stem.split("_")[1]
            file_date = datetime.strptime(timestamp_str, "%Y%m%d")

            # Remove if older than retention period
            if file_date < cutoff_date:
                file.unlink()
        except (ValueError, IndexError):
            # Skip files with invalid names
            continue
