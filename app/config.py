"""Configuration for calendar sync."""

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


class CalendarConfig:
    """Calendar configuration."""

    default_format: str = "ics"
    calendar_dir: Path = Path("data/calendars")
    ls_default_limit: int = 5
    calendar_git_remote_url: Optional[str] = None

    @classmethod
    def from_env(cls) -> "CalendarConfig":
        """Load configuration from environment variables and .env file."""
        # Load .env file if python-dotenv is available
        if load_dotenv is not None:
            load_dotenv()

        config = cls()
        if "CALENDAR_FORMAT" in os.environ:
            config.default_format = os.environ["CALENDAR_FORMAT"]
        if "CALENDAR_DIR" in os.environ:
            config.calendar_dir = Path(os.environ["CALENDAR_DIR"])
        if "LS_DEFAULT_LIMIT" in os.environ:
            try:
                config.ls_default_limit = int(os.environ["LS_DEFAULT_LIMIT"])
            except ValueError:
                pass  # Keep default if invalid
        if "CALENDAR_GIT_REMOTE_URL" in os.environ:
            config.calendar_git_remote_url = os.environ["CALENDAR_GIT_REMOTE_URL"]
        return config
