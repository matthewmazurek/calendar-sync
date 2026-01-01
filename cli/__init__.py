"""CLI package for calendar sync tool."""

import logging

from cli.parser import main

# Configure logging (only to file, not stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("calendar_sync.log"),
    ],
)

__all__ = ["main"]
