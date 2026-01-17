"""Pure formatting functions for display output."""

from datetime import date, datetime, timezone


def format_relative_time(dt: datetime) -> str:
    """Format datetime as relative time.

    Args:
        dt: Datetime to format.

    Returns:
        Formatted time string (e.g., "2h ago", "1w ago", "3mo ago", "1y ago").
    """
    if dt.tzinfo is None:
        # If no timezone, assume UTC
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    time_diff = now - dt

    if time_diff.days == 0:
        if time_diff.seconds < 60:  # Less than 1 minute
            return "just now"
        elif time_diff.seconds < 3600:  # Less than 1 hour
            minutes = time_diff.seconds // 60
            return f"{minutes}m ago"
        else:  # Less than 24 hours
            hours = time_diff.seconds // 3600
            return f"{hours}h ago"
    elif time_diff.days < 7:
        return f"{time_diff.days}d ago"
    elif time_diff.days < 30:
        # Weeks (1-4 weeks)
        weeks = time_diff.days // 7
        return f"{weeks}w ago"
    elif time_diff.days < 365:
        # Months (1-11 months)
        months = time_diff.days // 30
        return f"{months}mo ago"
    else:
        # Years
        years = time_diff.days // 365
        return f"{years}y ago"


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Formatted size string (e.g., "1.5KB", "2.3MB").
    """
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TB"


def format_datetime(
    dt: datetime | date | None,
    include_relative: bool = True,
) -> str:
    """Format datetime or date with optional relative time.

    Args:
        dt: Datetime or date to format, or None.
        include_relative: Whether to include relative time suffix.

    Returns:
        Formatted datetime string, or "N/A" if dt is None.
    """
    if dt is None:
        return "N/A"

    # Handle date objects (no time component)
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")

    # Handle datetime objects
    # Ensure timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    if include_relative:
        relative = format_relative_time(dt)
        return f"{date_str} ({relative})"
    return date_str
