"""Configuration for calendar sync."""

import os
from pathlib import Path

from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


class CalendarConfig(BaseModel):
    """Calendar configuration with Pydantic validation."""

    calendar_dir: Path = Field(default=Path("data/calendars"))
    ls_default_limit: int = Field(default=5, ge=1)
    calendar_git_remote_url: str | None = None
    default_template: str | None = None
    template_dir: Path = Field(default=Path("data/templates"))

    @classmethod
    def from_env(cls) -> "CalendarConfig":
        """Load configuration from environment variables and .env file."""
        # Load .env file if python-dotenv is available
        if load_dotenv is not None:
            load_dotenv()

        # Build config dict from environment
        config_dict = {}
        if "CALENDAR_DIR" in os.environ:
            config_dict["calendar_dir"] = Path(os.environ["CALENDAR_DIR"])
        if "LS_DEFAULT_LIMIT" in os.environ:
            try:
                config_dict["ls_default_limit"] = int(os.environ["LS_DEFAULT_LIMIT"])
            except ValueError:
                pass  # Keep default if invalid
        if "CALENDAR_GIT_REMOTE_URL" in os.environ:
            config_dict["calendar_git_remote_url"] = os.environ[
                "CALENDAR_GIT_REMOTE_URL"
            ]
        if "DEFAULT_TEMPLATE" in os.environ:
            config_dict["default_template"] = os.environ["DEFAULT_TEMPLATE"]
        if "TEMPLATE_DIR" in os.environ:
            config_dict["template_dir"] = Path(os.environ["TEMPLATE_DIR"])

        return cls(**config_dict)
