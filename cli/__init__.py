"""CLI package for calendar sync tool."""

import logging
import sys
from pathlib import Path

from app.config import CalendarConfig


def setup_logging(
    verbose: bool = False, quiet: bool = False, config: CalendarConfig | None = None
) -> None:
    """Configure logging with separate formatters for file and console.

    Args:
        verbose: If True, set console to DEBUG level
        quiet: If True, set console to ERROR level only
        config: Optional CalendarConfig for log directory/filename settings
    """
    if config is None:
        config = CalendarConfig.from_env()

    # File formatter: includes timestamp
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Console formatter: no timestamp, just level and message
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")

    # Ensure logs directory exists
    config.log_dir.mkdir(exist_ok=True)

    # File handler (with timestamp)
    file_handler = logging.FileHandler(config.log_dir / config.log_filename)
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)

    # Console handler - level based on flags
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(console_formatter)

    if quiet:
        console_handler.setLevel(logging.ERROR)
    elif verbose:
        console_handler.setLevel(logging.INFO)
    else:
        # Default: only show warnings and errors (no INFO spam)
        console_handler.setLevel(logging.WARNING)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def main() -> None:
    """Main entry point for the CLI."""
    from cli.parser import app

    app()


__all__ = ["main", "setup_logging"]
