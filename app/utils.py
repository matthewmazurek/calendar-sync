"""Utility functions for calendar-sync."""

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


@contextmanager
def temp_file_path(suffix: str = "") -> Generator[Path, None, None]:
    """
    Context manager that provides a temp file path and cleans up on exit.

    Usage:
        with temp_file_path(suffix=".ics") as path:
            path.write_bytes(content)
            # use path...
        # path is automatically deleted

    Args:
        suffix: File suffix (e.g., ".ics", ".json")

    Yields:
        Path to temporary file
    """
    path = Path(tempfile.mktemp(suffix=suffix))
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)
