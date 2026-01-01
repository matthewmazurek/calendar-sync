"""Configuration for calendar sync."""

import os
from pathlib import Path


class CalendarConfig:
    """Calendar configuration."""

    default_format: str = "ics"
    calendar_dir: Path = Path("data/calendars")

    @classmethod
    def from_env(cls) -> "CalendarConfig":
        """Load configuration from environment variables."""
        config = cls()
        if "CALENDAR_FORMAT" in os.environ:
            config.default_format = os.environ["CALENDAR_FORMAT"]
        if "CALENDAR_DIR" in os.environ:
            config.calendar_dir = Path(os.environ["CALENDAR_DIR"])
        return config
