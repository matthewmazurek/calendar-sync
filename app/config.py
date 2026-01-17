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

    # Storage paths
    calendar_dir: Path = Field(default=Path("data/calendars"))
    template_dir: Path = Field(default=Path("data/templates"))
    log_dir: Path = Field(default=Path("logs"))

    # File naming
    canonical_filename: str = Field(default="data.json")
    settings_filename: str = Field(default="config.json")
    ics_export_filename: str = Field(default="calendar.ics")
    log_filename: str = Field(default="calendar_sync.log")

    # Templates
    default_template: str = Field(default="default")

    # Git settings
    calendar_git_remote_url: str | None = None
    git_default_remote: str = Field(default="origin")
    git_default_branch: str = Field(default="main")

    # CLI defaults
    ls_default_limit: int = Field(default=5, ge=1)

    @classmethod
    def from_env(cls) -> "CalendarConfig":
        """Load configuration from environment variables and .env file."""
        # Load .env file if python-dotenv is available
        if load_dotenv is not None:
            load_dotenv()

        # Build config dict from environment
        config_dict = {}

        # Storage paths
        if "CALENDAR_DIR" in os.environ:
            config_dict["calendar_dir"] = Path(os.environ["CALENDAR_DIR"])
        if "TEMPLATE_DIR" in os.environ:
            config_dict["template_dir"] = Path(os.environ["TEMPLATE_DIR"])
        if "LOG_DIR" in os.environ:
            config_dict["log_dir"] = Path(os.environ["LOG_DIR"])

        # File naming
        if "LOG_FILENAME" in os.environ:
            config_dict["log_filename"] = os.environ["LOG_FILENAME"]

        # Templates
        if "DEFAULT_TEMPLATE" in os.environ:
            config_dict["default_template"] = os.environ["DEFAULT_TEMPLATE"]

        # Git settings
        if "CALENDAR_GIT_REMOTE_URL" in os.environ:
            config_dict["calendar_git_remote_url"] = os.environ[
                "CALENDAR_GIT_REMOTE_URL"
            ]
        if "GIT_DEFAULT_REMOTE" in os.environ:
            config_dict["git_default_remote"] = os.environ["GIT_DEFAULT_REMOTE"]
        if "GIT_DEFAULT_BRANCH" in os.environ:
            config_dict["git_default_branch"] = os.environ["GIT_DEFAULT_BRANCH"]

        # CLI defaults
        if "LS_DEFAULT_LIMIT" in os.environ:
            try:
                config_dict["ls_default_limit"] = int(os.environ["LS_DEFAULT_LIMIT"])
            except ValueError:
                pass  # Keep default if invalid

        return cls(**config_dict)
