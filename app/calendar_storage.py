import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from flask import current_app

# Default calendar directory
DEFAULT_CALENDAR_DIR = Path("data/calendars")
# Default retention period in days
DEFAULT_RETENTION_DAYS = 30


def get_calendar_dir() -> Path:
    """Get the calendar directory from config or use default."""
    return Path(current_app.config.get("CALENDAR_DIR", DEFAULT_CALENDAR_DIR))


def get_retention_days() -> int:
    """Get the retention period from config or use default."""
    return current_app.config.get("CALENDAR_RETENTION_DAYS", DEFAULT_RETENTION_DAYS)


def ensure_calendar_dir():
    """Ensure the calendar directory exists."""
    get_calendar_dir().mkdir(parents=True, exist_ok=True)


def save_calendar(ical_content: bytes) -> str:
    """
    Save a calendar file with timestamp and return the filename.

    Args:
        ical_content: The iCalendar content as bytes

    Returns:
        The filename of the saved calendar
    """
    ensure_calendar_dir()
    calendar_dir = get_calendar_dir()

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
    cleanup_old_calendars()

    return filename


def get_latest_calendar() -> Optional[bytes]:
    """
    Get the content of the latest calendar file.

    Returns:
        The calendar content as bytes, or None if no calendar exists
    """
    latest_path = get_calendar_dir() / "latest-calendar.ics"
    if not latest_path.exists():
        return None

    with open(latest_path, "rb") as f:
        return f.read()


def cleanup_old_calendars():
    """Remove calendar files older than the retention period."""
    calendar_dir = get_calendar_dir()
    retention_days = get_retention_days()
    cutoff_date = datetime.now() - timedelta(days=retention_days)

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
