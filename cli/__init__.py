"""CLI package for calendar sync tool."""

import logging
import sys
from pathlib import Path

from cli.parser import main

# Configure logging with separate formatters for file and console
# File formatter: includes timestamp
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Console formatter: no timestamp, just level and message
console_formatter = logging.Formatter("%(levelname)s: %(message)s")

# Ensure logs directory exists
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# File handler (with timestamp)
file_handler = logging.FileHandler(logs_dir / "calendar_sync.log")
file_handler.setFormatter(file_formatter)
file_handler.setLevel(logging.INFO)

# Console handler (no timestamp) - show info, warnings and errors
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setFormatter(console_formatter)
console_handler.setLevel(logging.INFO)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

__all__ = ["main"]
