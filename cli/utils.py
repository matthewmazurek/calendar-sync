"""CLI utilities for logging and output formatting."""

import logging
from datetime import datetime, timezone
from typing import Dict

logger = logging.getLogger(__name__)


def format_processing_summary(
    processing_summary: Dict, ingestion_summary: Dict | None = None
) -> None:
    """
    Format and display processing summary.

    Args:
        processing_summary: Dictionary with input_counts, output_counts, input_total, output_total
        ingestion_summary: Optional dictionary with weekly coverage stats
    """
    if not processing_summary:
        return

    input_counts = processing_summary.get("input_counts", {})
    output_counts = processing_summary.get("output_counts", {})
    input_total = processing_summary.get("input_total", 0)
    output_total = processing_summary.get("output_total", 0)

    if input_counts:
        print("Processing (Event type: count):")
        for event_type, count in sorted(input_counts.items()):
            output_count = output_counts.get(event_type, 0)
            if output_count != count:
                print(f"  - {event_type}: {count} (Collapsed to {output_count})")
            else:
                print(f"  - {event_type}: {count}")

        if output_total != input_total:
            print(f"  - Total: {input_total} (Collapsed to {output_total})")
        else:
            print(f"  - Total: {input_total}")

    if ingestion_summary:
        total_halfdays = ingestion_summary.get("total_halfdays")
        weekly_coverage_year = ingestion_summary.get("weekly_coverage_year")
        if total_halfdays is not None or weekly_coverage_year is not None:
            print("Statistics:")
        if total_halfdays is not None:
            print(f"  - Half-days booked: {total_halfdays}")
        if weekly_coverage_year is not None:
            print(f"  - Coverage: {weekly_coverage_year:.1f} half days per week")


def format_relative_time(commit_date: datetime) -> str:
    """
    Format datetime as relative time for recent commits.

    Args:
        commit_date: Datetime to format

    Returns:
        Formatted time string (e.g., "2h ago", "1w ago", "3mo ago", "1y ago")
    """
    if commit_date.tzinfo is None:
        # If no timezone, assume UTC
        commit_date = commit_date.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    time_diff = now - commit_date

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
    """
    Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted size string (e.g., "1.5KB", "2.3MB")
    """
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TB"
