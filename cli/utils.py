"""CLI utilities for logging and output formatting."""

import logging
from datetime import datetime, timezone
from typing import Dict

logger = logging.getLogger(__name__)


def format_processing_summary(processing_summary: Dict) -> None:
    """
    Format and display processing summary.

    Args:
        processing_summary: Dictionary with input_counts, output_counts, input_total, output_total
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


def format_complete_summary(
    ingestion_summary: Dict | None = None,
    processing_summary: Dict | None = None,
    action_message: str | None = None,
    filepath: str | None = None,
    published: bool = False,
) -> None:
    """
    Format and display complete summary at the end of sync operation.

    Args:
        ingestion_summary: Dictionary with format, reader_name, events, date_range, year, revised_date
        processing_summary: Dictionary with input_counts, output_counts, input_total, output_total
        action_message: Message about calendar creation/update
        filepath: Path to saved calendar file
        published: Whether calendar was published to git
    """
    print()  # Empty line before summary
    print("─" * 60)
    print("Summary")
    print("─" * 60)

    if ingestion_summary:
        print("Data ingestion:")
        print(
            f"  - Format: {ingestion_summary.get('format')} ({ingestion_summary.get('reader_name')})"
        )
        print(f"  - Events: {ingestion_summary.get('events')}")
        print(f"  - Date range: {ingestion_summary.get('date_range')}")
        if ingestion_summary.get("year"):
            print(f"  - Year: {ingestion_summary.get('year')}")
        if ingestion_summary.get("revised_date"):
            print(f"  - Revised date: {ingestion_summary.get('revised_date')}")
        print()

    if processing_summary:
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
            print()

    if action_message:
        print(action_message)

    if filepath:
        # Determine if it's a create or update based on action_message
        if action_message and "Creating" in action_message:
            print(f"Writing: Calendar created at {filepath}")
        else:
            print(f"Writing: Calendar updated at {filepath}")

    if published:
        print("Publishing: Calendar published to git")


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
